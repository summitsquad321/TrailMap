"""
Centralised configuration loader.

Reads variables from one of three sources (highest->lowest priority):
1. st.secrets (when running inside Streamlit)
2. Environment variables
3. .env file (loaded via python-dotenv)
"""
from functools import lru_cache
import os
from pathlib import Path

try:
    import streamlit as st
except ImportError:          # ingest_service runs outside Streamlit
    st = None                # pragma: no cover

from dotenv import load_dotenv

# Look for a .env file one directory above the package root
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


@lru_cache
def get(key: str) -> str:
    """
    Return the config value for *key*, raising KeyError if not found.
    """
    # 1. Streamlit secrets
    if st is not None and key in st.secrets:
        return st.secrets[key]

    # 2. Environment
    if key in os.environ:
        return os.environ[key]

    # 3. Missing
    raise KeyError(
        f"Config '{key}' not found. "
        "Set it in `.streamlit/secrets.toml`, an environment variable, or `.env`."
    )
