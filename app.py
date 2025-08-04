import streamlit as st, json
try:
    json.loads(st.secrets["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
    st.success("✅ Secret is valid JSON")
except Exception as e:
    st.error(f"❌ Still invalid: {e}")
