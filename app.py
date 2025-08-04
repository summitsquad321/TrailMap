import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json, time, os

# Build creds exactly like firestore_utils.py
creds = service_account.Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
)
db = firestore.Client(project=st.secrets["FIRESTORE_PROJECT_ID"], credentials=creds)

start = time.perf_counter()
try:
    count = len(list(db.collections()))
    elapsed = time.perf_counter() - start
    st.success(f"🔥 Firestore ping OK – {count} top-level collections in {elapsed:.2f}s")
except Exception as e:
    st.exception(e)
