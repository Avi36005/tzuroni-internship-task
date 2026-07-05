#!/bin/bash
# One-command launcher for the full Weather Prediction AI Trading Terminal.
# Starts the FastAPI backend + Streamlit dashboard together.
# Usage: ./run.sh
cd "$(dirname "$0")"
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi
PYTHONPATH=. python scripts/run_app.py
