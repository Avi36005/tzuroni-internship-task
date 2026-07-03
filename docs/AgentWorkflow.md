# Agent Workflow & Orchestration

This document details the coordination logic, communication flow, and payload validation executed by the **Supervisor Agent** (Agent 10) during each trading cycle.

---

## 🔁 Complete Orchestration Sequence

Each run cycle executes the following sequence:

```
[Start Cycle]
      │
      ▼
1. Settle Expired Contracts  ◄── Fetch weather for yesterday's coordinates and pay out $1.00/share
      │
      ▼
2. Fetch Active Markets      ◄── Queries Polymarket API or activates Weather-Forecast Simulator
      │
      ▼
3. Run Specialized Agents (Loop per active market):
   ├── WeatherIntelAgent     ◄── Fetch 10-day forecasts (Open-Meteo)
   ├── LocalWeatherAgent     ◄── Fetch official localized alerts (NOAA)
   ├── ResearchAgent         ◄── Scrape news & social networks (DuckDuckGo news/sentiment)
   ├── PredictionAgent       ◄── Run quantitative models & write reasoning (calibrated prior/likelihood)
   ├── RiskAgent             ◄── Run fractional Kelly sizing & verify portfolio drawdown limits
   └── ExecutionAgent        ◄── Submit orders, calculate slippage, commit records
      │
      ▼
4. Run Hedging Agent         ◄── Scan position concentrations and execute correlation hedges
      │
      ▼
5. Update Portfolio          ◄── Revalue all assets & calculate Sharpe/Sortino ratios
      │
      ▼
[End Cycle]
```

---

## 📦 Agent Data Exchange Schemas

Specialist agents communicate using structured JSON payloads to ensure data consistency and prevent hallucinations.

### 1. Research Agent (Agent 4) Output
```json
{
  "summary": "AI summary of recent regional weather updates and alerts",
  "sentiment_score": 0.35,  // range [-1.0 (dry/hot/clear) to 1.0 (stormy/heavy rain)]
  "confidence": 0.85        // range [0.0 to 1.0]
}
```

### 2. Prediction Agent (Agent 5) Output
```json
{
  "probability": 0.68,      // Calibrated probability of outcome
  "confidence": 0.78,       // Confidence in predictability
  "decision": "BUY YES",    // BUY YES, BUY NO, or NO TRADE
  "edge": 0.18,             // model probability - market odds
  "expected_value": 0.18,   // EV per share purchased
  "reasoning": "Calibrated forecast probability of 68% exceeds market YES price of 50 cents."
}
```

### 3. Risk Management Agent (Agent 6) Output
```json
{
  "status": "APPROVED",     // APPROVED or REJECTED
  "allocated_fraction": 0.045, // percentage of portfolio allocation
  "allocated_dollars": 450.0,  // dollar amount allocated
  "reason": "Fractional Kelly size of 4.5% is compliant with maximum exposure limit of 10%."
}
```

---

## 🛡️ Failure Detection, Retry & Validation

The Supervisor Agent implements a robust transaction shield:
1. **API Key Fallback:** If `OPENROUTER_API_KEY` is not present, all agents trigger self-contained, pre-structured analytical fallback engines, guaranteeing that execution does not crash.
2. **APIFY to Open-Meteo Transition:** If Apify scrapers fail, they transition instantly to Open-Meteo & NOAA clients.
3. **Data Constraint Validation:** All LLM JSON responses are passed through regular expression filters to extract the JSON block. If keys are missing, the supervisor reconstructs them using statistical mathematical outputs (e.g. calculating edge directly from model and market variables).
