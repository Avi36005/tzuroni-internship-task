"""
One-command launcher for the full Weather Prediction AI Trading Terminal.

Starts BOTH services and wires them together:
  1. FastAPI backend  -> http://127.0.0.1:8000  (REST API + /run-workflow)
  2. Streamlit dashboard -> http://localhost:8501  (interactive UI)

From the dashboard's "Settings & Terminal Control" page you can then press
"🚀 Trigger Agent Cycle" to run the whole multi-agent workflow and watch trades,
predictions, portfolio and risk update live — all in the browser.

Usage:
    PYTHONPATH=. python scripts/run_app.py
    # or simply:  ./run.sh

Press Ctrl+C once to shut both services down cleanly.
"""
import os
import subprocess
import sys
import time
import urllib.request

BACKEND_HEALTH_URL = "http://127.0.0.1:8000/portfolio/state"
DASHBOARD_URL = "http://localhost:8501"


def _env() -> dict:
    env = os.environ.copy()
    # Ensure `import app...` works regardless of where the script is launched from.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _wait_for_backend(timeout: float = 40.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(BACKEND_HEALTH_URL, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    env = _env()
    procs = []

    print("=" * 60)
    print("🚀 Launching Weather Prediction AI Trading Terminal")
    print("=" * 60)

    # 1. Backend (FastAPI + Uvicorn)
    print("→ Starting FastAPI backend on http://127.0.0.1:8000 ...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        env=env,
    )
    procs.append(backend)

    if not _wait_for_backend():
        print("❌ Backend failed to start within timeout. Shutting down.")
        backend.terminate()
        return 1
    print("✅ Backend is up.")

    # 2. Streamlit dashboard
    print(f"→ Starting Streamlit dashboard on {DASHBOARD_URL} ...")
    dashboard = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app/dashboard/app.py",
            "--server.port", "8501",
            "--server.headless", "true",
        ],
        env=env,
    )
    procs.append(dashboard)

    print("\n" + "=" * 60)
    print(f"✅ App is running.  Open the dashboard:  {DASHBOARD_URL}")
    print("   Go to 'Settings & Terminal Control' → 'Trigger Agent Cycle'")
    print("   Press Ctrl+C here to stop everything.")
    print("=" * 60 + "\n")

    try:
        # Exit if either process dies.
        while all(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
