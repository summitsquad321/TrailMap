"""
Typed, well-documented Firestore accessor layer.

All database interactions flow through the helpers below,
making unit-testing and future refactors simple.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account

from .config import get

# ─── Firestore initialisation ────────────────────────────────────────────────
_client: Optional[firestore.Client] = None


def _sanitize_key_json(raw: str) -> str:
    """
    • Strip leading / trailing whitespace (incl. the newline inserted right
      after the opening triple-quotes in Streamlit Secrets).

    • Replace *only* the physical CR/LF characters **inside** the
      ``"private_key"`` value with the two-character escape sequence ``\\n``.

      New-lines elsewhere (between fields) are valid JSON whitespace and are
      therefore preserved.
    """
    raw = raw.strip()

    def _fix(match: re.Match[str]) -> str:              # match group = key body
        body: str = match.group(1).replace("\r", "").replace("\n", "\\n")
        return f'"private_key":"{body}"'

    # (?s) = DOTALL → .* spans multiple lines
    pattern = re.compile(r'"private_key"\s*:\s*"(.*?)"', flags=re.S)
    return pattern.sub(_fix, raw)


def _write_tmp_keyfile() -> str:
    """
    Clean the JSON, validate with ``json.loads``, write to /tmp, and return the
    path.  The temp file disappears on container restart.
    """
    cleaned = _sanitize_key_json(st.secrets["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
    json.loads(cleaned)                     # raises if still malformed

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    tmp.write(cleaned.encode("utf-8"))
    tmp.flush()
    return tmp.name


def client() -> firestore.Client:
    """
    Lazily build & cache a Firestore client using the service-account key
    materialised to /tmp.
    """
    global _client
    if _client is None:
        key_path = _write_tmp_keyfile()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path  # for ADC reuse

        creds = service_account.Credentials.from_service_account_file(key_path)
        _client = firestore.Client(
            project=get("FIRESTORE_PROJECT_ID"),
            credentials=creds,
        )
    return _client

# ---  Camera CRUD -------------------------------------------------------------
CAMERA_COL = "cameras"


def create_camera(camera_id: str, nickname: str, lat: float, lon: float) -> None:
    """
    Atomically create a new camera document.

    Raises:
        ValueError: if the camera_id already exists.
    """
    ref = client().collection(CAMERA_COL).document(camera_id)
    if ref.get().exists:
        raise ValueError(f"Camera '{camera_id}' already exists.")
    ref.set(
        {
            "nickname": nickname,
            "lat": lat,
            "lon": lon,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )


def update_camera(camera_id: str, **fields) -> None:
    """
    Update one or more mutable fields (nickname, lat, lon).

    Non-existent camera raises ValueError.
    """
    ref = client().collection(CAMERA_COL).document(camera_id)
    if not ref.get().exists:
        raise ValueError(f"Camera '{camera_id}' not found.")
    fields["updated_at"] = datetime.utcnow()
    ref.update(fields)


def delete_camera(camera_id: str) -> None:
    """
    Delete camera and optionally cascade (detections remain for audit).

    Raises ValueError if camera doesn't exist.
    """
    ref = client().collection(CAMERA_COL).document(camera_id)
    if not ref.get().exists:
        raise ValueError(f"Camera '{camera_id}' not found.")
    ref.delete()


def list_cameras(as_dataframe: bool = False) -> List[Dict]:
    """
    Retrieve all camera documents.

    Returns:
        • list of dicts   (default)
        • pandas.DataFrame  if *as_dataframe* True
    """
    docs = [doc.to_dict() | {"camera_id": doc.id} for doc in client().collection(CAMERA_COL).stream()]
    return pd.DataFrame(docs) if as_dataframe else docs


# ---  Detections --------------------------------------------------------------
DETECT_COL = "detections"
ROLLUP_COL = "daily_rollups"


def ingest_detections(rows: List[Dict]) -> None:
    """
    Batch-write incoming detection rows.

    Each row MUST contain:
        file_name, date_time, buck_count, deer_count, doe_count, camera_id
    """
    batch = client().batch()
    detect_ref = client().collection(DETECT_COL)
    camera_cache = {c["camera_id"] for c in list_cameras()}

    for row in rows:
        cam_id = row["camera_id"]
        if cam_id not in camera_cache:
            raise ValueError(f"Unknown camera_id '{cam_id}' – create camera first.")

        doc_ref = detect_ref.document()
        batch.set(
            doc_ref,
            {
                **row,
                "date_time": firestore.SERVER_TIMESTAMP
                if row["date_time"] == "NOW"
                else row["date_time"],
                "ingested_at": datetime.utcnow(),
            },
        )

    batch.commit()


def get_detections_df() -> pd.DataFrame:
    """
    Fetch *all* detections into a DataFrame (lazy load for app startup).

    If volume grows, replace with paginated generator + caching.
    """
    docs = (doc.to_dict() for doc in client().collection(DETECT_COL).stream())
    df = pd.DataFrame(docs)
    # Cast
    if not df.empty:
        df["date_time"] = pd.to_datetime(df["date_time"])
    return df
