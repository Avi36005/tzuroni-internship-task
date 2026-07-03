# Deployment Guide

The Weather Prediction AI Trading Agent can be deployed locally using virtual environments or containerized using Docker and Docker Compose.

---

## 💻 Local Machine Deployment

### Prerequisites
- Python 3.12 or newer
- git

### Step 1: Clone and Set Up Virtualenv
Initialize the directory and create a virtual environment:
```bash
git clone <repository_url> weather-market-ai
cd weather-market-ai

# Create virtual environment with uv (fast) or venv
uv venv --python 3.12
source .venv/bin/activate
```

### Step 2: Install Package Dependencies
```bash
uv pip install -r requirements.txt
uv pip install git+https://github.com/NousResearch/hermes-agent.git
```

### Step 3: Configure Environment
Copy `.env.example` to `.env` and fill in your OpenRouter API key and desired models:
```bash
cp .env.example .env
# Edit .env using nano or vim
```

### Step 4: Run the Backend & Frontend
Start the FastAPI server (backend):
```bash
PYTHONPATH=. uv run python app/main.py
```

In another terminal, activate the environment and start the Streamlit interface (frontend):
```bash
uv run streamlit run app/dashboard/app.py
```
Go to `http://localhost:8501` to access the trading terminal.

---

## 🐳 Docker Container Deployment

Docker Compose builds the images and sets up both the FastAPI backend and Streamlit dashboard containers, sharing a local SQLite file.

### Step 1: Start Services
```bash
docker-compose up --build
```

This starts:
- **FastAPI Backend (`http://localhost:8000`)**: Running uvicorn. Exposes REST endpoints and runs database initializations.
- **Streamlit Frontend (`http://localhost:8501`)**: Running the web dashboard terminal.

### Step 2: Trigger Workflows in Docker
You can trigger agent workflows inside Docker either by:
1. Clicking the **Trigger Agent Cycle** button under the **Settings** page in the Streamlit UI.
2. Sending a HTTP POST request to the backend:
```bash
curl -X POST http://localhost:8000/run-workflow
```

### Step 3: Tear Down
To stop and remove containers and networks:
```bash
docker-compose down
```
