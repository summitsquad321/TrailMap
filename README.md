# 🦌 TrailMap

Interactive **Streamlit** dashboard + **FastAPI** ingest micro-service for visualising and managing trail-camera activity **across time and space**.

---

## Features Overview

| Area | Highlights |
|------|------------|
| **Interactive Map** | Pydeck scatter layer shows one point per camera.<br>• Hover → nickname, image stats, last-seen.<br>• Sidebar filters: date-range, hour slider, camera multi-select.<br>• **Camera CRUD** right in the UI (add, edit, delete). |
| **Data Ingest** | 1️⃣ Manual CSV upload (browser).<br>2️⃣ **DeerLens POST** endpoint (`/api/ingest`).<br>CSV rows are validated then stored in Firestore (`detections/`, `daily_rollups/`). |
| **Maintenance** | Browse detections, bulk **re-assign** rows to new `camera_id`. |
| **Persistence** | On launch, TrailMap loads cameras + detections from Firestore so historical data is always available. |
| **Typed Firestore Utils** | Single point of truth for batched writes & reads, making tests/refactors trivial. |

---

## Repository Layout

```text
.
├── ingest_service.py         # FastAPI server for DeerLens uploads
├── requirements.txt
├── trailmap/
│   ├── config.py             # centralised env config
│   ├── firestore_utils.py    # all Firestore access
│   └── pages/                # Streamlit multi-page app
│       ├── 01_Map.py
│       ├── 02_Upload.py
│       └── 03_Maintenance.py
└── .streamlit/
    ├── config.toml           # UI theme & server opts
 
