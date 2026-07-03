# System Architecture

The Weather Prediction AI Trading Agent is designed as a modular, distributed, multi-agent quantitative trading system. It utilizes standard Python asyncio constructs and interfaces with third-party meteorological and news search services.

---

## 📂 System Directory Structure

```
weather-market-ai/
├── app/
│   ├── config/             # Pydantic Settings & Environment Loading
│   ├── database/           # Async SQLite Database & SQLAlchemy ORM
│   ├── weather/            # Open-Meteo & NOAA meteorological client integrations
│   ├── research/           # DuckDuckGo search client integrations
│   ├── markets/            # Polymarket API & Simulator engine fallback
│   ├── prediction/         # Bayesian & Ensemble forecasting ML models
│   ├── risk/               # Kelly Criterion formulas & portfolio shields
│   ├── hedging/            # Cross-city correlation hedging calculators
│   ├── paper_trader/       # PnL accounting & payout settlement systems
│   ├── portfolio/          # Portfolio stats (Sharpe, Sortino, PnL)
│   ├── dashboard/          # Streamlit UI & Plotly charts
│   ├── prompts/            # Agent personality prompts
│   ├── agents/             # The 10 specialized Hermes agents
│   └── main.py             # FastAPI backend API entry point
├── tests/                  # Pytest unit & integration tests
├── scripts/                # Utility & CLI demo execution scripts
├── requirements.txt        # Package dependencies
├── Dockerfile              # Container deployment recipe
├── docker-compose.yml      # Orchestration of backend and frontend
└── README.md               # Quickstart and overview
```

---

## 🤖 Multi-Agent Workflow Engine

The multi-agent system comprises 10 specialized agent roles:

### 1. Information Gathering (Data Layer Agents)
*   **Weather Intelligence Agent (Agent 1):** Connects to the global Open-Meteo endpoint to collect daily temperature, precipitation, pressure, wind, and alerts.
*   **Local Weather Research Agent (Agent 2):** Connects to NOAA's endpoint for US-based points to gather granular meteorological warnings and alerts.
*   **Market Agent (Agent 3):** Fetches active weather contracts from the Polymarket Client. Retrieves price metrics, daily volume, spread, and liquidity.

### 2. Research & Reasoning (Intelligence Layer Agents)
*   **Research Agent (Agent 4):** Scrapes the web (via DuckDuckGo) for storm warnings, cyclones, news reports, and social media chatter, mapping text snippets to sentiment scores.
*   **Prediction Agent (Agent 5):** Combines datasets from Agents 1, 2, 3, and 4. Applies a Bayesian-derived calibrated forecast model to output final probabilities, edges, and trade decisions.

### 3. Sizing, Execution & Risk (Trading Layer Agents)
*   **Risk Management Agent (Agent 6):** Evaluates predicted edges against contract costs, running fractional Kelly formulas and verifying Value-at-Risk limits.
*   **Execution Agent (Agent 7):** Executes paper orders through a simulated order book walker, logging trade slippage and costs.
*   **Portfolio Agent (Agent 8):** Audits capital accounts, calculates unrealized/realized PnL, and computes risk-adjusted Sharpe and Sortino ratios.
*   **Hedging Agent (Agent 9):** Evaluates position concentrations and executes cross-city correlation hedge trades.

### 4. Orchestration (Orchestrator Agent)
*   **Supervisor Agent (Agent 10):** Directs execution schedules, coordinates communication between specialist agents, seeds defaults, and handles settlement payouts of expired contracts.
