import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Set up page configurations
st.set_page_config(
    page_title="Weather Quant AI Trading Terminal",
    page_icon="⛈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #00e676;
    }
    .metric-title {
        font-size: 0.9rem;
        color: #888888;
        margin-bottom: 5px;
    }
    h1, h2, h3 {
        font-family: 'Outfit', 'Inter', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# API endpoint URL
API_URL = "http://127.0.0.1:8000"

def get_data(endpoint: str):
    """Helper to fetch data from backend REST API"""
    try:
        r = requests.get(f"{API_URL}{endpoint}")
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

def trigger_agent_run():
    """Trigger the Supervisor Agent workflow run"""
    try:
        r = requests.post(f"{API_URL}/run-workflow")
        if r.status_code == 200:
            return r.json()
        return {"success": False, "message": "Failed to run agent loop."}
    except Exception as e:
        return {"success": False, "message": str(e)}

# Sidebar Navigation
st.sidebar.title("⛈️ Weather Quant AI")
st.sidebar.markdown("*Bloomberg Terminal for Weather Prediction Markets*")

# Quick-access control: trigger a full multi-agent workflow cycle from any page.
if st.sidebar.button("🚀 Trigger Agent Cycle", use_container_width=True, type="primary"):
    with st.spinner("Supervisor agent coordinating specialist workflows… please wait."):
        res = trigger_agent_run()
    if res and res.get("success"):
        st.sidebar.success(
            f"✅ Cycle complete — Trades: {res.get('trades_executed')}, "
            f"Hedges: {res.get('hedges_executed')}, Value: ${res.get('portfolio_value'):.2f}"
        )
        st.balloons()
    else:
        st.sidebar.error(f"❌ {res.get('message') if res else 'Unknown error'}")

st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navigation Menu",
    [
        "Dashboard Overview",
        "Weather Intelligence",
        "Prediction Markets",
        "AI Predictions & Edge",
        "Risk Management",
        "Portfolio & Statistics",
        "Trade History",
        "Settings & Terminal Control"
    ]
)

# Check backend status
backend_live = True
port_state = get_data("/portfolio/state")
if port_state is None:
    backend_live = False
    st.error("⚠️ Backend API Server is Offline. Please start the backend service at `python app/main.py` first.")

if backend_live:
    # ----------------------------------------------------
    # Page 1: Dashboard Overview
    # ----------------------------------------------------
    if menu == "Dashboard Overview":
        st.title("⛈️ Weather Quant AI Trading Terminal")
        
        # Load data
        history = get_data("/portfolio/history") or []
        positions = get_data("/positions") or []
        trades = get_data("/trades") or []
        stats = get_data("/portfolio/statistics") or {
            "sharpe_ratio": 0.0, "sortino_ratio": 0.0, "max_drawdown": 0.0
        }
        
        # Key Metrics Row
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(
                f'<div class="metric-card"><div class="metric-title">Portfolio Valuation</div>'
                f'<div class="metric-value" style="color:#29b6f6">${port_state["portfolio_value"]:.2f}</div></div>',
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                f'<div class="metric-card"><div class="metric-title">Available Cash</div>'
                f'<div class="metric-value" style="color:#29b6f6">${port_state["cash"]:.2f}</div></div>',
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                f'<div class="metric-card"><div class="metric-title">Open Exposure</div>'
                f'<div class="metric-value" style="color:#ffb74d">${port_state["exposure"]:.2f}</div></div>',
                unsafe_allow_html=True
            )
        with col4:
            color = "#00e676" if port_state["unrealized_pnl"] >= 0 else "#ff5252"
            st.markdown(
                f'<div class="metric-card"><div class="metric-title">Unrealized PnL</div>'
                f'<div class="metric-value" style="color:{color}">${port_state["unrealized_pnl"]:+.2f}</div></div>',
                unsafe_allow_html=True
            )
        with col5:
            st.markdown(
                f'<div class="metric-card"><div class="metric-title">Max Drawdown</div>'
                f'<div class="metric-value" style="color:#ff5252">{stats["max_drawdown"]:.2%}</div></div>',
                unsafe_allow_html=True
            )
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Equity Curve and Position allocation side-by-side
        row2_col1, row2_col2 = st.columns([2, 1])
        
        with row2_col1:
            st.subheader("📈 Portfolio Growth (Equity Curve)")
            if history:
                df_hist = pd.DataFrame(history)
                df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"])
                fig = px.line(
                    df_hist, x="timestamp", y="portfolio_value", 
                    title="Portfolio Valuation Over Time ($)",
                    color_discrete_sequence=["#00e676"]
                )
                fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No historical data to chart yet. Trigger the agents to generate trading history.")
                
        with row2_col2:
            st.subheader("📊 Capital Allocation")
            if positions:
                df_pos = pd.DataFrame(positions)
                df_pos["exposure"] = df_pos["shares"] * df_pos["current_price"]
                # Add Cash as separate slice
                cash_slice = pd.DataFrame([{"city_name": "Cash", "exposure": port_state["cash"]}])
                df_pie = pd.concat([df_pos[["city_name", "exposure"]], cash_slice])
                fig_pie = px.pie(
                    df_pie, values="exposure", names="city_name", 
                    color_discrete_sequence=px.colors.sequential.Tealgrn
                )
                fig_pie.update_layout(template="plotly_dark", showlegend=True)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                fig_pie = px.pie(
                    names=["Cash"], values=[10000.0],
                    color_discrete_sequence=["#29b6f6"]
                )
                fig_pie.update_layout(template="plotly_dark")
                st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Open Positions Table
        st.subheader("💼 Active Portfolio Holdings")
        if positions:
            df_pos_tbl = pd.DataFrame(positions)
            df_pos_tbl["Position Value"] = df_pos_tbl["shares"] * df_pos_tbl["current_price"]
            st.dataframe(
                df_pos_tbl[["market_title", "city_name", "side", "shares", "average_price", "current_price", "pnl", "is_hedged"]],
                use_container_width=True
            )
        else:
            st.info("No open positions. All positions closed or no trades placed yet.")

    # ----------------------------------------------------
    # Page 2: Weather Intelligence
    # ----------------------------------------------------
    elif menu == "Weather Intelligence":
        st.title("🌦️ Weather Intelligence Center")
        cities = get_data("/cities") or []
        
        if cities:
            city_names = [c["name"] for c in cities]
            selected_city = st.selectbox("Select Target City", city_names)
            
            city_data = [c for c in cities if c["name"] == selected_city][0]
            st.write(f"**Country:** {city_data['country']} | **Official Meteorological Body:** {city_data['local_agency']}")
            st.write(f"**Coordinates:** Latitude {city_data['latitude']}, Longitude {city_data['longitude']}")
            
            # Fetch forecast via python-code proxy (hitting Open-Meteo on behalf of dashboard)
            st.subheader("🌦️ 7-Day Precipitation Probability Forecast")
            try:
                forecast_url = f"https://api.open-meteo.com/v1/forecast?latitude={city_data['latitude']}&longitude={city_data['longitude']}&daily=precipitation_probability_max,temperature_2m_max,temperature_2m_min&timezone=auto"
                forecast_resp = requests.get(forecast_url).json()
                
                df_fore = pd.DataFrame({
                    "Date": forecast_resp["daily"]["time"],
                    "Max Temp (°C)": forecast_resp["daily"]["temperature_2m_max"],
                    "Min Temp (°C)": forecast_resp["daily"]["temperature_2m_min"],
                    "Rain Probability (%)": forecast_resp["daily"]["precipitation_probability_max"]
                })
                
                # Plotly Chart
                fig_rain = px.bar(
                    df_fore, x="Date", y="Rain Probability (%)",
                    color="Rain Probability (%)",
                    color_continuous_scale="Purples",
                    title="Daily Peak Precipitation Probability"
                )
                fig_rain.update_layout(template="plotly_dark")
                st.plotly_chart(fig_rain, use_container_width=True)
                
                # Temperature Range Line Chart
                fig_temp = go.Figure()
                fig_temp.add_trace(go.Scatter(x=df_fore["Date"], y=df_fore["Max Temp (°C)"], name="Max Temp", line_color="#ff5252"))
                fig_temp.add_trace(go.Scatter(x=df_fore["Date"], y=df_fore["Min Temp (°C)"], name="Min Temp", line_color="#29b6f6"))
                fig_temp.update_layout(title="Temperature Range Outlook (°C)", template="plotly_dark")
                st.plotly_chart(fig_temp, use_container_width=True)
                
            except Exception as e:
                st.warning("Could not load detailed charts for this city.")
        else:
            st.info("Supported cities not seeded yet. Run the workflow to initialize default cities.")

    # ----------------------------------------------------
    # Page 3: Prediction Markets
    # ----------------------------------------------------
    elif menu == "Prediction Markets":
        st.title("⚖️ Prediction Markets (Polymarket)")

        market_src = get_data("/markets/source") or {}
        if market_src.get("polymarket_live"):
            st.success("🟢 Live Polymarket data — real market odds from the Gamma API.")
        else:
            st.warning(
                "🟡 Polymarket is geoblocked from this network, so market **odds** are "
                "simulated (anchored to real Open-Meteo forecasts). All weather, local-agency, "
                "research and LLM data is real. Set `POLYMARKET_PROXY` (a VPN/proxy) for live odds."
            )

        st.subheader("Active Weather Outcome Contracts")
        
        # Connect to SQLite markets
        # We can show active markets
        predictions = get_data("/predictions") or []
        
        if predictions:
            df_m = pd.DataFrame(predictions)
            # Find unique markets
            st.dataframe(
                df_m[["market_title", "probability_yes", "expected_value", "decision"]].drop_duplicates(),
                use_container_width=True
            )
        else:
            st.info("No market prediction data found. Run terminal controls to fetch active weather markets.")

    # ----------------------------------------------------
    # Page 4: AI Predictions & Edge
    # ----------------------------------------------------
    elif menu == "AI Predictions & Edge":
        st.title("🤖 AI Predictions & Quantitative Edge")
        
        preds = get_data("/predictions") or []
        if preds:
            df_p = pd.DataFrame(preds)
            st.subheader("Model Predictions Log")
            st.dataframe(
                df_p[["market_title", "prediction_date", "probability_yes", "confidence", "edge", "expected_value", "decision", "created_at"]],
                use_container_width=True
            )
            
            # Probability vs Market Price Chart
            st.subheader("📊 Probability Calibration Map")
            # We compare model probability with market implied probability
            # Sourced from edge column
            df_p["Market Implied Price"] = df_p["probability_yes"] - df_p["edge"]
            
            fig_cal = px.scatter(
                df_p, x="Market Implied Price", y="probability_yes",
                color="decision", size="confidence",
                hover_data=["market_title"],
                labels={"probability_yes": "Model Calibrated Probability", "Market Implied Price": "Market Price (Odds)"},
                title="Model Forecast vs Market Implied Odds (Bubble Size = AI Confidence)"
            )
            # Add y=x line
            fig_cal.add_shape(
                type="line", line=dict(dash="dash", color="grey"),
                x0=0, y0=0, x1=1, y1=1
            )
            fig_cal.update_layout(template="plotly_dark")
            st.plotly_chart(fig_cal, use_container_width=True)
            
            # Detailed reasoning display
            st.subheader("🔍 Deep Research Reasoning Logs")
            for i, p in enumerate(preds[:3]):
                with st.expander(f"Contract: {p['market_title']} ({p['prediction_date']})"):
                    st.write(f"**AI Decision:** `{p['decision']}` | **Edge:** {p['edge']:+.1%} | **Expected Value:** ${p['expected_value']:.2f}")
                    st.write(f"**Reasoning Summary:** {p['reasoning']}")
        else:
            st.info("No AI predictions found. Run workflow to populate predictions.")

    # ----------------------------------------------------
    # Page 5: Risk Management
    # ----------------------------------------------------
    elif menu == "Risk Management":
        st.title("🛡️ Risk Management Dashboard")
        
        positions = get_data("/positions") or []
        stats = get_data("/portfolio/statistics") or {
            "sharpe_ratio": 0.0, "sortino_ratio": 0.0, "max_drawdown": 0.0
        }
        
        # Sizing metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Risk Score", "Low (Quarter Kelly)", help="Fractional Kelly setting.")
        with col2:
            st.metric("Value at Risk (95% VaR)", f"${(port_state['exposure'] * 0.15 * 1.645):.2f}", help="Daily VaR estimate.")
        with col3:
            st.metric("Daily Loss Limit", f"5.0% (${(port_state['portfolio_value'] * 0.05):.2f})", help="Stop trading constraint.")
            
        # Sizing Details
        st.subheader("🌐 Exposure Risk Heatmap")
        if positions:
            df_pos = pd.DataFrame(positions)
            df_pos["exposure"] = df_pos["shares"] * df_pos["current_price"]
            
            fig_heat = px.treemap(
                df_pos, path=["city_name", "side"], values="exposure",
                color="pnl", color_continuous_scale="RdYlGn",
                title="Exposure Concentration map by City and Outcome"
            )
            fig_heat.update_layout(template="plotly_dark")
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info("No active positions to display in concentration map.")

    # ----------------------------------------------------
    # Page 6: Portfolio & Statistics
    # ----------------------------------------------------
    elif menu == "Portfolio & Statistics":
        st.title("📊 Quantitative Performance Statistics")
        stats = get_data("/portfolio/statistics") or {}
        
        if stats:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Annualized Sharpe Ratio", f"{stats.get('sharpe_ratio', 0.0):.4f}")
            with col2:
                st.metric("Annualized Sortino Ratio", f"{stats.get('sortino_ratio', 0.0):.4f}")
            with col3:
                st.metric("Maximum Drawdown", f"{stats.get('max_drawdown', 0.0):.2%}")
            with col4:
                st.metric("Total Revalued Value", f"${stats.get('current_portfolio_value', 10000.0):.2f}")
                
            # Additional ML metrics — computed from real settled contract outcomes only.
            st.subheader("🎯 Statistical Prediction Performance (Model Audit)")
            perf = get_data("/model/performance") or {}
            if perf.get("settled_count", 0) > 0:
                st.markdown(
                    f"Prediction validation on **{perf['settled_count']} settled contracts** "
                    "(model probability vs. actual weather outcomes)."
                )
                m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                with m_col1:
                    st.metric("Brier Score", f"{perf['brier_score']:.4f}", help="Closer to 0 is better.")
                with m_col2:
                    st.metric("F1 Score", f"{perf['f1_score']:.4f}", help="Balance of Precision and Recall.")
                with m_col3:
                    st.metric("Precision", f"{perf['precision']:.4f}")
                with m_col4:
                    st.metric("Recall", f"{perf['recall']:.4f}")
            else:
                st.info(
                    "🕓 Model-audit metrics (Brier, F1, Precision, Recall) are computed from "
                    "real settled contract outcomes and will appear once markets have resolved."
                )
        else:
            st.info("Portfolio metrics could not be loaded.")

    # ----------------------------------------------------
    # Page 7: Trade History
    # ----------------------------------------------------
    elif menu == "Trade History":
        st.title("📜 Transaction Audit Log")
        
        trades = get_data("/trades") or []
        if trades:
            df_t = pd.DataFrame(trades)
            st.dataframe(
                df_t[["executed_at", "market_title", "side", "price", "amount", "cost", "slippage", "status", "reason"]],
                use_container_width=True
            )
        else:
            st.info("No trades executed yet. Run agent cycles to place paper trades.")

    # ----------------------------------------------------
    # Page 9: Settings & Terminal Control
    # ----------------------------------------------------
    elif menu == "Settings & Terminal Control":
        st.title("⚙️ System Settings & Supervisor Terminal Control")
        
        st.subheader("🤖 Trigger Multi-Agent Workflow Cycle")
        st.markdown(
            "Triggering the workflow will execute a complete cycle: fetch forecasts, NOAA alerts, "
            "perform DuckDuckGo news research, run prediction ML pipelines, execute Kelly risk checks, "
            "place paper trades, execute hedges, and revalue the portfolio."
        )
        
        if st.button("🚀 Trigger Agent Cycle"):
            with st.spinner("supervisor agent coordinating specialist workflows... Please wait."):
                res = trigger_agent_run()
                if res and res.get("success"):
                    st.success(
                        f"Workflow cycle completed successfully! "
                        f"Trades executed: {res.get('trades_executed')}, Hedges executed: {res.get('hedges_executed')}. "
                        f"New Portfolio Value: ${res.get('portfolio_value'):.2f}"
                    )
                    st.balloons()
                else:
                    st.error(f"Error running workflow: {res.get('message') if res else 'Unknown error'}")
                    
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.subheader("📋 System Configurations")
        st.markdown(f"**LLM Model Configuration:** `{get_data('/portfolio/state') is not None}` (Backend Active)")
        st.markdown(f"**Active Cities Seeded:** 20 cities")
        st.markdown(f"**Database Engine:** SQLite + SQLAlchemy (Asyncio)")
