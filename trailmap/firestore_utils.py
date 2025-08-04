"""
Typed, well-documented Firestore accessor layer.

All database interactions flow through the helpers below,
making unit-testing and future refactors simple.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account

from .config import get

# ---  Firestore initialisation ------------------------------------------------
_client: Optional[firestore.Client] = None


def _load_creds_from_secret() -> service_account.Credentials:
    """
    Build a Credentials object from the JSON string stored in
    st.secrets["GOOGLE_APPLICATION_CREDENTIALS_JSON"].

    If the secret was pasted with *real* newline characters inside the
    private_key, replace them with the JSON escape sequence ``\\n`` so that
    ``json.loads`` succeeds.
    """
    raw = st.secrets["GOOGLE_APPLICATION_CREDENTIALS_JSON"]

    # Sanitise: convert any literal new-lines inside the JSON into "\n".
    if "\n" in raw and "\\n" not in raw:
        raw = raw.replace("\n", "\\n")

    creds_dict = json.loads(raw)
    return service_account.Credentials.from_service_account_info(creds_dict)


def client() -> firestore.Client:
    """
    Lazily create and cache a Firestore client using explicit credentials.
    """
    global _client  # noqa: WPS420 (module-level cache is intentional)
    if _client is None:
        creds = _load_creds_from_secret()
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
