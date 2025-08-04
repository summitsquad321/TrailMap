"""
Streamlit Page ▸ Maintenance  🧹

• Browse detections
• Re-assign camera_id (data hygiene)
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from trailmap.firestore_utils import get_detections_df, list_cameras, ingest_detections

st.set_page_config(page_title="TrailMap – Maintenance", layout="wide")

st.title("🧹 Data Maintenance")

df = get_detections_df()
if df.empty:
    st.info("No detections ingested yet.")
    st.stop()

grid_df = df[["file_name", "date_time", "camera_id", "buck_count", "doe_count", "deer_count"]]
st.dataframe(grid_df, use_container_width=True)

st.markdown("### Re-assign Camera")
to_fix = st.multiselect("Select rows by file_name", grid_df["file_name"])
if to_fix:
    cameras = [c["camera_id"] for c in list_cameras()]
    new_cam = st.selectbox("New camera_id", cameras)
    if st.button("Update rows"):
        mask = df["file_name"].isin(to_fix)
        rows = df[mask].copy()
        rows["camera_id"] = new_cam
        ingest_detections(rows.to_dict(orient="records"))  # overwrite as new docs
        st.success(f"Re-assigned {mask.sum()} rows to camera {new_cam}.")
        st.experimental_rerun()
