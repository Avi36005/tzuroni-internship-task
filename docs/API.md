# API Documentation

The Weather Prediction AI Trading Agent backend is built with FastAPI. It exposes REST API endpoints for terminal dashboard integration and autonomous execution controls.

---

## 🚀 Core Endpoints

### 1. Run Workflow
Trigger a complete cycle of the multi-agent prediction, risk sizing, and trading loop.
- **URL:** `/run-workflow`
- **Method:** `POST`
- **Response Format:**
```json
{
  "success": true,
  "trades_executed": 3,
  "hedges_executed": 1,
  "portfolio_value": 10000.0,
  "cash": 9400.0
}
```

### 2. Portfolio State
Retrieve the current capital structure, position exposure, and PnL metrics.
- **URL:** `/portfolio/state`
- **Method:** `GET`
- **Response Format:**
```json
{
  "cash": 9400.0,
  "portfolio_value": 10025.50,
  "unrealized_pnl": 25.50,
  "daily_return": 0.0025,
  "exposure": 600.0,
  "max_drawdown": 0.0,
  "timestamp": "2026-07-02T15:30:19.453"
}
```

### 3. Portfolio History
Fetch historical valuation data to plot equity curves.
- **URL:** `/portfolio/history`
- **Method:** `GET`
- **Response Format:**
```json
[
  {
    "timestamp": "2026-07-02T15:00:00",
    "portfolio_value": 10000.0,
    "cash": 10000.0,
    "exposure": 0.0,
    "unrealized_pnl": 0.0
  },
  {
    "timestamp": "2026-07-02T15:30:19",
    "portfolio_value": 10025.50,
    "cash": 9400.0,
    "exposure": 600.0,
    "unrealized_pnl": 25.50
  }
]
```

### 4. Active Positions
Fetch all currently open paper trading contract positions.
- **URL:** `/positions`
- **Method:** `GET`
- **Response Format:**
```json
[
  {
    "id": 1,
    "market_slug": "will-it-rain-in-new-york-2026-07-03",
    "market_title": "Will it rain in New York tomorrow?",
    "city_name": "New York",
    "side": "YES",
    "shares": 909.09,
    "average_price": 0.22,
    "current_price": 0.25,
    "pnl": 27.27,
    "is_hedged": false
  }
]
```

### 5. Trade History
Fetch complete transaction log history.
- **URL:** `/trades`
- **Method:** `GET`
- **Response Format:**
```json
[
  {
    "id": 1,
    "market_slug": "will-it-rain-in-new-york-2026-07-03",
    "market_title": "Will it rain in New York tomorrow?",
    "side": "YES",
    "price": 0.22,
    "amount": 909.09,
    "cost": 200.0,
    "reason": "Rain probability high based on NWS forecast",
    "status": "FILLED",
    "slippage": 0.015,
    "executed_at": "2026-07-02T15:08:04"
  }
]
```

### 6. AI Predictions
Fetch prediction edge reasoning and probability logs.
- **URL:** `/predictions`
- **Method:** `GET`
- **Response Format:**
```json
[
  {
    "id": 1,
    "market_title": "Will it rain in New York tomorrow?",
    "prediction_date": "2026-07-03",
    "probability_yes": 0.65,
    "probability_no": 0.35,
    "confidence": 0.85,
    "edge": 0.43,
    "expected_value": 0.43,
    "decision": "BUY YES",
    "reasoning": "Calibrated ensemble model indicates 65% probability of rain vs 22% market odds.",
    "created_at": "2026-07-02T15:08:04"
  }
]
```
