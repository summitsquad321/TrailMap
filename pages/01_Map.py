"""
Streamlit Page ▸ Map  🗺️

• Interactive Pydeck map with one point per camera.
• Hover tooltip: nickname, total images, buck %, doe %, last-seen.
• Sidebar filters and camera CRUD.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import pydeck as pdk

from trailmap.firestore_utils import (
    list_cameras,
    get_detections_df,
    create_camera,
    update_camera,
    delete_camera,
)

st.set_page_config(page_title="TrailMap – Cameras", layout="wide")

# -----------------------------------------------------------------------------#
# Sidebar – Filters                                                            #
# -----------------------------------------------------------------------------#
st.sidebar.title("Filters")

det_df = get_detections_df()      # expensive → cached by Streamlit

# Date-range filter -----------------------------------------------------------#
if det_df.empty:
    min_date = max_date = pd.Timestamp.today().normalize()
else:
    min_date, max_date = det_df["date_time"].min(), det_df["date_time"].max()

date_range = st.sidebar.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)

hour_range = st.sidebar.slider("Hour of day", 0, 23, (0, 23), step=1)

# Camera multiselect (list auto-refreshes when CRUD happens) ------------------#
camera_list = list_cameras()
camera_ids: list[str] = [c["camera_id"] for c in camera_list]
selected_cameras = st.sidebar.multiselect("Cameras", camera_ids, default=camera_ids)

# -----------------------------------------------------------------------------#
# Camera CRUD                                                                  #
# -----------------------------------------------------------------------------#
st.sidebar.markdown("---")
st.sidebar.subheader("Manage Cameras")

crud_action = st.sidebar.radio(
    "Action", ["Add Camera", "Edit Camera", "Delete Camera"], horizontal=True
)

if crud_action == "Add Camera":
    with st.sidebar.form("add_form"):
        st.info("Click on the map or enter coordinates manually.")
        new_id = st.text_input("Camera ID")
        nickname = st.text_input("Nickname")
        lat = st.number_input("Latitude", format="%.6f")
        lon = st.number_input("Longitude", format="%.6f")
        submitted = st.form_submit_button("Create")
        if submitted:
            try:
                create_camera(new_id, nickname, lat, lon)
                st.success(f"Camera '{new_id}' created.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

elif crud_action == "Edit Camera":
    target = st.sidebar.selectbox("Select camera", camera_ids)
    cam_doc = next(c for c in camera_list if c["camera_id"] == target)
    with st.sidebar.form("edit_form"):
        nickname = st.text_input("Nickname", value=cam_doc["nickname"])
        lat = st.number_input("Latitude", value=cam_doc["lat"], format="%.6f")
        lon = st.number_input("Longitude", value=cam_doc["lon"], format="%.6f")
        submitted = st.form_submit_button("Update")
        if submitted:
            update_camera(target, nickname=nickname, lat=lat, lon=lon)
            st.success("Updated.")
            st.rerun()

else:  # Delete
    target = st.sidebar.selectbox("Select camera", camera_ids)
    if st.sidebar.button("Delete camera", type="primary"):
        delete_camera(target)
        st.success(f"Camera '{target}' deleted.")
        st.rerun()

# -----------------------------------------------------------------------------#
# Map Rendering                                                                #
# -----------------------------------------------------------------------------#
# Aggregate detection metrics fast -------------------------------------------#
if det_df.empty:
    agg_df = pd.DataFrame(columns=["camera_id", "total", "buck_pct", "doe_pct", "last_seen"])
else:
    masked = det_df[
        (det_df["camera_id"].isin(selected_cameras))
        & (det_df["date_time"].dt.date.between(*date_range))
        & (det_df["date_time"].dt.hour.between(*hour_range))
    ]
    agg_df = (
        masked.groupby("camera_id")
        .agg(
            total=("file_name", "count"),
            buck_cnt=("buck_count", "sum"),
            doe_cnt=("doe_count", "sum"),
            last_seen=("date_time", "max"),
        )
        .reset_index()
    )
    agg_df["buck_pct"] = (agg_df["buck_cnt"] / agg_df["total"]).round(2)
    agg_df["doe_pct"] = (agg_df["doe_cnt"] / agg_df["total"]).round(2)

# Combine with camera coords --------------------------------------------------#
cam_df = pd.DataFrame(camera_list)
full_df = cam_df.merge(agg_df, on="camera_id", how="left").fillna({"total": 0, "buck_pct": 0, "doe_pct": 0})

# Pydeck layer ----------------------------------------------------------------#
tooltip = {
    "html": "<b>{nickname}</b><br/>Images: {total}<br/>Buck %: {buck_pct}<br/>"
    "Doe %: {doe_pct}<br/>Last-seen: {last_seen}",
    "style": {"color": "white"},
}

layer = pdk.Layer(
    "ScatterplotLayer",
    data=full_df,
    get_position="[lon, lat]",
    get_radius=50,
    get_fill_color=[8, 160, 69, 160],  # RGBA
    pickable=True,
)

view_state = pdk.ViewState(
    latitude=float(full_df["lat"].mean()) if not full_df.empty else 40,
    longitude=float(full_df["lon"].mean()) if not full_df.empty else -80,
    zoom=5,
    pitch=0,
)

st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip), use_container_width=True)

# NOTE: Clicking a point to load gallery/charts would be implemented by listening
#       to deckgl events via st.pydeck_chart's returned JSON – omitted for brevity.
