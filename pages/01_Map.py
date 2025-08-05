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

import io, base64
from PIL import Image, ImageDraw

# ── 8-point compass → degrees clockwise from North ─────────
COMPASS_DEG = {
    "N": 0,  "NE": 45,  "E": 90,  "SE": 135,
    "S": 180,"SW": 225, "W": 270, "NW": 315,
}

def make_red_pin_data_url() -> tuple[str, int, int]:
    """
    Returns a ('data:image/png;base64,…', width, height) triple
    for a red inverted-teardrop pin ~48 × 64 px.
    Runs only once per session.
    """
    W, H = 48, 64
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Round head
    draw.ellipse([0, 0, W, W], fill=(220, 0, 0, 255))

    # Pointed tail  ↓
    draw.polygon([(W // 2, H), (0, W // 2), (W, W // 2)],
                 fill=(220, 0, 0, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}", W, H

pdk.settings.mapbox_api_key = st.secrets["MAPBOX_TOKEN"]

from trailmap.firestore_utils import (
    list_cameras,
    get_detections_df,
    create_camera,
    update_camera,
    delete_camera,
)

st.set_page_config(page_title="TrailMap – Cameras", layout="wide")

# ─────────────────────────── Sidebar – Filters ──────────────────────────────
st.sidebar.title("Filters")

det_df = get_detections_df()           # cached by Streamlit

# ── Map "direction" strings to degrees ─────────────────────
if "direction" in det_df.columns:
    det_df["direction_deg"] = (
        det_df["direction"].str.upper()           # e.g. "sw" → "SW"
              .map(COMPASS_DEG)                   # unknown / blank → NaN
    )
else:
    det_df["direction_deg"] = np.nan

if det_df.empty:
    min_date = max_date = pd.Timestamp.today().normalize()
else:
    min_date, max_date = det_df["date_time"].min(), det_df["date_time"].max()

date_range = st.sidebar.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
hour_range = st.sidebar.slider("Hour of day", 0, 23, (0, 23), step=1)

camera_list = list_cameras()
camera_ids = [c["camera_id"] for c in camera_list]
selected_cameras = st.sidebar.multiselect("Cameras", camera_ids, default=camera_ids)

# ─────────────────────────── Sidebar – Camera CRUD ──────────────────────────
st.sidebar.markdown("---")
st.sidebar.subheader("Manage Cameras")

crud_action = st.sidebar.radio(
    "Action", ["Add Camera", "Edit Camera", "Delete Camera"], horizontal=True
)

if crud_action == "Add Camera":
    with st.sidebar.form("add_form"):
        st.info("Click on the map or enter coordinates manually.")
        new_id   = st.text_input("Camera ID")
        nickname = st.text_input("Nickname")
        lat      = st.number_input("Latitude",  format="%.6f")
        lon      = st.number_input("Longitude", format="%.6f")
        if st.form_submit_button("Create"):
            try:
                create_camera(new_id, nickname, lat, lon)
                st.success(f"Camera '{new_id}' created.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

elif crud_action == "Edit Camera":
    target  = st.sidebar.selectbox("Select camera", camera_ids)
    cam_doc = next(c for c in camera_list if c["camera_id"] == target)
    with st.sidebar.form("edit_form"):
        nickname = st.text_input("Nickname", value=cam_doc["nickname"])
        lat      = st.number_input("Latitude",  value=cam_doc["lat"], format="%.6f")
        lon      = st.number_input("Longitude", value=cam_doc["lon"], format="%.6f")
        if st.form_submit_button("Update"):
            update_camera(target, nickname=nickname, lat=lat, lon=lon)
            st.success("Updated.")
            st.rerun()

else:  # Delete
    target = st.sidebar.selectbox("Select camera", camera_ids)
    if st.sidebar.button("Delete camera", type="primary"):
        delete_camera(target)
        st.success(f"Camera '{target}' deleted.")
        st.rerun()

# ─────────────────────────── Map Rendering ──────────────────────────────────
# Aggregate detection metrics
if det_df.empty:
    agg_df = pd.DataFrame(
        columns=["camera_id", "total", "buck_pct", "doe_pct", "last_seen"]
    )
else:
    mask   = (
        det_df["camera_id"].isin(selected_cameras)
        & det_df["date_time"].dt.date.between(*date_range)
        & det_df["date_time"].dt.hour.between(*hour_range)
    )
    agg_df = (
        det_df[mask]
        .groupby("camera_id")
        .agg(
            total     = ("file_name", "count"),
            buck_cnt  = ("buck_count", "sum"),
            doe_cnt   = ("doe_count",  "sum"),
            last_seen = ("date_time",  "max"),
        )
        .reset_index()
    )
    agg_df["buck_pct"] = (agg_df["buck_cnt"] / agg_df["total"]).round(2)
    agg_df["doe_pct"]  = (agg_df["doe_cnt"]  / agg_df["total"]).round(2)

# ── Predominant travel direction per camera in current slice ─
if det_df.empty:
    heading_df = pd.DataFrame(columns=["camera_id", "heading"])
else:
    # For each camera, take the MODE of direction_deg
    heading_df = (
        det_df[mask & det_df["direction_deg"].notna()]
          .groupby("camera_id")["direction_deg"]
          .agg(lambda s: s.mode().iat[0])   # first value if tie
          .reset_index(name="heading")
    )

# Combine with camera coords
cam_df  = pd.DataFrame(camera_list).dropna(subset=["lat", "lon"])
full_df = (
    cam_df.merge(agg_df, on="camera_id", how="left")
    .fillna({"total": 0, "buck_pct": 0, "doe_pct": 0})
)

arrow_df = cam_df.merge(heading_df, on="camera_id", how="inner")
ARROW_URL, ARROW_W, ARROW_H = make_arrow_data_url()
ARROW_ICON = {"url": ARROW_URL, "width": ARROW_W, "height": ARROW_H,
              "anchorY": ARROW_H//2}
arrow_df["icon_data"] = [ARROW_ICON] * len(arrow_df)


# ── Inject a base-64 pin icon ──────────────────────────────────
PIN_URL, PIN_W, PIN_H = make_red_pin_data_url()
PIN_ICON = {
    "url": PIN_URL,
    "width": PIN_W,
    "height": PIN_H,
    "anchorY": PIN_H,      # bottom-center anchoring
}
full_df["icon_data"] = [PIN_ICON] * len(full_df)

if full_df.empty:
    st.info("Add a camera with latitude & longitude to see it on the map.")
    st.stop()

pin_layer = pdk.Layer(          #  <-- must come *before* deck = pdk.Deck
    "IconLayer",
    id="camera-pins",
    data=full_df,
    get_icon="icon_data",
    get_position="[lon, lat]",
    get_size=4,
    size_scale=12,
    pickable=True,
)

def make_arrow_data_url() -> tuple[str, int, int]:
    """Returns ('data:image/png;base64,…', W, H) for a white up-arrow."""
    W = H = 64
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # shaft
    draw.rectangle([(W//2 - 5, H//4), (W//2 + 5, H*3//4)], fill=(255,255,255,255))
    # head
    draw.polygon([(W//2, 0), (W//2 - 15, H//4), (W//2 + 15, H//4)],
                 fill=(255,255,255,255))
    buf = io.BytesIO(); img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}", W, H

arrow_layer = pdk.Layer(
    "IconLayer",
    id="travel-arrows",
    data=arrow_df,
    get_icon="icon_data",
    get_position="[lon, lat]",
    get_angle="heading",        # rotate arrow client-side
    get_size=3,                 # a bit smaller than pins
    size_scale=8,
    pickable=False,
)

tooltip = {
    "html": (
        "<b>{nickname}</b><br/>Images: {total}<br/>"
        "Buck %: {buck_pct}<br/>Doe %: {doe_pct}<br/>Last seen: {last_seen}"
    ),
    "style": {"color": "white"},
}

view_state = pdk.ViewState(
    latitude=41.7048,      # Cherry Grove, PA
    longitude=-79.1453,
    zoom=11,               # township-scale; tweak 10-12 to taste
    pitch=0,
)

# Default Mapbox Streets style (no map_style parameter)
deck = pdk.Deck(
    layers              = [pin_layer, arrow_layer],
    initial_view_state  = view_state,
    tooltip             = tooltip,
    map_provider        = "mapbox",
    map_style           = "mapbox://styles/mapbox/outdoors-v12",
    api_keys={"mapbox": st.secrets["MAPBOX_TOKEN"]},
)

st.pydeck_chart(deck, use_container_width=True)
