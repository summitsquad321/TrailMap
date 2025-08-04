"""
FastAPI-based ingestion micro-service.

Runs **outside Streamlit** so DeerLens can send POST requests
without blocking the UI process.

Run locally:
    uvicorn ingest_service:app --reload --port 8080
"""
from __future__ import annotations

import csv
import io
from typing import List

from fastapi import FastAPI, Header, HTTPException, status, Request
from pydantic import BaseModel, Field

from trailmap.firestore_utils import ingest_detections

# -----------------------------------------------------------------------------#
# Simple token-based auth                                                      #
# -----------------------------------------------------------------------------#
API_TOKEN = "replace-me-or-use-env"  # 👉 ENV var in production

app = FastAPI(title="TrailMap Ingest API")


def _check_auth(auth_header: str | None) -> None:
    if auth_header != f"Bearer {API_TOKEN}":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# -----------------------------------------------------------------------------#
# POST /api/ingest                                                             #
# -----------------------------------------------------------------------------#
class DetectionRow(BaseModel):
    file_name: str
    date_time: str
    buck_count: int = Field(ge=0)
    deer_count: int = Field(ge=0)
    doe_count: int = Field(ge=0)
    camera_id: str


@app.post("/api/ingest", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_endpoint(
    request: Request,
    authorization: str | None = Header(None),
):
    """
    Accept raw CSV payload in request body.  Performs:
        • auth check
        • csv → list[dict]
        • validation via `DetectionRow`
        • writes to Firestore
    """
    _check_auth(authorization)

    body = await request.body()
    try:
        # Decode
        csv_str = body.decode()
        reader = csv.DictReader(io.StringIO(csv_str))
        rows: List[DetectionRow] = [DetectionRow(**r) for r in reader]
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Malformed CSV: {exc}") from exc

    # Firestore write
    try:
        ingest_detections([r.model_dump() for r in rows])
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
"""
FastAPI-based ingestion micro-service.

Runs **outside Streamlit** so DeerLens can send POST requests
without blocking the UI process.

Run locally:
    uvicorn ingest_service:app --reload --port 8080
"""
from __future__ import annotations

import csv
import io
from typing import List

from fastapi import FastAPI, Header, HTTPException, status, Request
from pydantic import BaseModel, Field

from trailmap.firestore_utils import ingest_detections

# -----------------------------------------------------------------------------#
# Simple token-based auth                                                      #
# -----------------------------------------------------------------------------#
API_TOKEN = "replace-me-or-use-env"  # 👉 ENV var in production

app = FastAPI(title="TrailMap Ingest API")


def _check_auth(auth_header: str | None) -> None:
    if auth_header != f"Bearer {API_TOKEN}":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# -----------------------------------------------------------------------------#
# POST /api/ingest                                                             #
# -----------------------------------------------------------------------------#
class DetectionRow(BaseModel):
    file_name: str
    date_time: str
    buck_count: int = Field(ge=0)
    deer_count: int = Field(ge=0)
    doe_count: int = Field(ge=0)
    camera_id: str


@app.post("/api/ingest", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_endpoint(
    request: Request,
    authorization: str | None = Header(None),
):
    """
    Accept raw CSV payload in request body.  Performs:
        • auth check
        • csv → list[dict]
        • validation via `DetectionRow`
        • writes to Firestore
    """
    _check_auth(authorization)

    body = await request.body()
    try:
        # Decode
        csv_str = body.decode()
        reader = csv.DictReader(io.StringIO(csv_str))
        rows: List[DetectionRow] = [DetectionRow(**r) for r in reader]
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Malformed CSV: {exc}") from exc

    # Firestore write
    try:
        ingest_detections([r.model_dump() for r in rows])
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
