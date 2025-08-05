"""
Streamlit Page ▸ Upload  ⬆️

Two modalities:
1. Manual CSV upload (browser).
2. Instructions & token for DeerLens to POST directly to /api/ingest.
"""
from __future__ import annotations

import csv
import io
from typing import List

import pandas as pd
import streamlit as st

from trailmap.firestore_utils import ingest_detections, list_cameras, create_camera

st.set_page_config(page_title="TrailMap – Upload", layout="wide")
st.title("📤 Data Upload / Ingest")

# ─────────────────────────── 1. Manual CSV Upload ────────────────────────────
st.header("1. Manual CSV Upload")
uploaded = st.file_uploader("Select DeerLens-formatted CSV", type="csv")

if uploaded:
    # Safe CSV load ───────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(uploaded)
    except Exception as e:                          # ParserError, UnicodeError …
        st.error(f"❌ Could not read CSV file:\n\n{e}")
        st.stop()

    # Add camera picker if column missing ─────────────────────────────────────
    if "camera_id" not in df.columns:
        st.warning(
            "CSV has no **camera_id** column. "
            "Choose which camera these rows belong to:"
        )
        existing_ids = [c["camera_id"] for c in list_cameras()]
        selected_cam = st.selectbox("Camera", existing_ids)
        df["camera_id"] = selected_cam

    st.write("Preview:", df.head())

    # Check for unknown cameras in the CSV  -----------------------------------
    camera_set   = {c["camera_id"] for c in list_cameras()}
    unknown_cams = sorted(set(df["camera_id"]) - camera_set)

    if unknown_cams:
        st.warning(f"Found {len(unknown_cams)} unknown camera_id(s): {unknown_cams}")
        with st.expander("Create missing cameras now"):
            for cam in unknown_cams:
                st.subheader(f"Camera {cam}")
                nick               = st.text_input(f"Nickname for {cam}", key=f"nick_{cam}")
                col1, col2         = st.columns(2)
                lat                = col1.number_input("Lat", key=f"lat_{cam}", format="%.6f")
                lon                = col2.number_input("Lon", key=f"lon_{cam}", format="%.6f")
                if st.button(f"Create {cam}", key=f"btn_{cam}"):
                    create_camera(cam, nick, lat, lon)
                    st.success(f"Camera {cam} added.  Re-run validation ⤵︎")
                    st.rerun()

    # Final submit ------------------------------------------------------------
    if st.button("Ingest rows ➜ Firestore"):
        try:
            ingest_detections(df.to_dict(orient="records"))
            st.success(f"Uploaded {len(df)} rows.")
        except ValueError as exc:
            st.error(str(exc))

st.markdown("---")

# ─────────────────────── 2. DeerLens direct POST Endpoint ────────────────────
st.header("2. POST Endpoint for DeerLens")
code = """
POST /api/ingest
Content-Type: text/csv
Authorization: Bearer <YOUR_API_TOKEN>

file_name,date_time,buck_count,deer_count,doe_count,camera_id
MUD_0276.JPG,2024-09-26 06:42:56,1,0,0,1
"""
st.code(code, language="bash")

st.info(
    "⚠️  The endpoint validates every `camera_id`. "
    "If any row references a non-existent camera, the request returns **HTTP 400** "
    "with a list of offending IDs so DeerLens can prompt you to fix them."
)
