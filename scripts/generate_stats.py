"""
Statistical results generator (assignment deliverable #3: "statistical results").

Runs the full multi-agent trading workflow for a configurable number of cycles, then
aggregates the resulting paper-trading performance into machine-readable (JSON) and
human-readable (Markdown) reports under ./results.

Usage:
    PYTHONPATH=. python scripts/generate_stats.py [num_cycles]
"""
import asyncio
import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.database.db import init_db, async_session
from app.database.models import City, Market, Prediction, Order, Position, PortfolioState
from app.agents.supervisor import SupervisorAgent
from app.agents.base import llm_configured, hermes_active, resolve_llm_config
from app.config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

RESULTS_DIR = Path("results")


async def collect_statistics(session) -> dict:
    """Aggregate trading statistics from the persisted database state."""
    cities = (await session.execute(select(City))).scalars().all()
    markets = (await session.execute(select(Market))).scalars().all()
    predictions = (await session.execute(select(Prediction))).scalars().all()
    orders = (await session.execute(select(Order))).scalars().all()
    positions = (await session.execute(select(Position))).scalars().all()

    port_states = (
        await session.execute(select(PortfolioState).order_by(PortfolioState.timestamp.asc()))
    ).scalars().all()

    starting_balance = settings.starting_balance
    latest = port_states[-1] if port_states else None
    final_value = latest.portfolio_value if latest else starting_balance
    total_return = (final_value - starting_balance) / starting_balance if starting_balance else 0.0

    # Decision distribution across all predictions.
    decision_counts = Counter(p.decision for p in predictions)

    # Cities that actually received at least one order (proves >= 5-city coverage).
    market_by_id = {m.id: m for m in markets}
    city_by_id = {c.id: c for c in cities}
    traded_city_names = set()
    for o in orders:
        mkt = market_by_id.get(o.market_id)
        if mkt:
            city = city_by_id.get(mkt.city_id)
            if city:
                traded_city_names.add(city.name)

    total_slippage = sum(o.slippage for o in orders) / len(orders) if orders else 0.0
    total_cost = sum(o.cost for o in orders)
    unrealized_pnl = sum(p.pnl for p in positions)
    avg_edge = sum(p.edge for p in predictions) / len(predictions) if predictions else 0.0
    avg_confidence = sum(p.confidence for p in predictions) / len(predictions) if predictions else 0.0

    # Reuse the portfolio manager's risk-adjusted metrics.
    supervisor = SupervisorAgent()
    stats = await supervisor.portfolio_agent.manager.calculate_portfolio_statistics(session)

    _, _, _, provider = resolve_llm_config()
    if not llm_configured():
        llm_mode = "deterministic-fallback"
    elif hermes_active():
        llm_mode = f"hermes-agent ({provider})"
    else:
        llm_mode = f"direct ({provider})"

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "llm_mode": llm_mode,
        "apify_enabled": bool(settings.apify_token),
        "capital": {
            "starting_balance": round(starting_balance, 2),
            "final_portfolio_value": round(final_value, 2),
            "total_return_pct": round(total_return * 100, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_capital_deployed": round(total_cost, 2),
        },
        "coverage": {
            "cities_supported": len(cities),
            "cities_traded": len(traded_city_names),
            "traded_city_names": sorted(traded_city_names),
            "markets_tracked": len(markets),
        },
        "activity": {
            "predictions_made": len(predictions),
            "orders_executed": len(orders),
            "open_positions": len(positions),
            "decision_distribution": dict(decision_counts),
            "avg_model_edge_pct": round(avg_edge * 100, 2),
            "avg_model_confidence": round(avg_confidence, 3),
            "avg_execution_slippage_pct": round(total_slippage * 100, 3),
        },
        "risk_adjusted_metrics": {
            "sharpe_ratio": stats["sharpe_ratio"],
            "sortino_ratio": stats["sortino_ratio"],
            "max_drawdown_pct": round(stats["max_drawdown"] * 100, 2),
            "daily_return_samples": stats.get("daily_returns_count", 0),
        },
    }


def render_markdown(report: dict) -> str:
    cap, cov, act, risk = report["capital"], report["coverage"], report["activity"], report["risk_adjusted_metrics"]
    lines = [
        "# Weather Prediction AI Agent — Statistical Results",
        "",
        f"_Generated: {report['generated_at']}_  ",
        f"_LLM mode: **{report['llm_mode']}** · Apify scraping enabled: **{report['apify_enabled']}**_",
        "",
        "## Capital & Returns",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Starting balance | ${cap['starting_balance']:,.2f} |",
        f"| Final portfolio value | ${cap['final_portfolio_value']:,.2f} |",
        f"| Total return | {cap['total_return_pct']:+.2f}% |",
        f"| Unrealized PnL | ${cap['unrealized_pnl']:+,.2f} |",
        f"| Capital deployed | ${cap['total_capital_deployed']:,.2f} |",
        "",
        "## Market Coverage",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Cities supported | {cov['cities_supported']} |",
        f"| Cities traded | {cov['cities_traded']} |",
        f"| Markets tracked | {cov['markets_tracked']} |",
        "",
        f"**Traded cities:** {', '.join(cov['traded_city_names']) or 'none'}",
        "",
        "## Trading Activity",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Predictions made | {act['predictions_made']} |",
        f"| Orders executed | {act['orders_executed']} |",
        f"| Open positions | {act['open_positions']} |",
        f"| Avg model edge | {act['avg_model_edge_pct']:+.2f}% |",
        f"| Avg model confidence | {act['avg_model_confidence']:.3f} |",
        f"| Avg execution slippage | {act['avg_execution_slippage_pct']:.3f}% |",
        "",
        f"**Decision distribution:** {act['decision_distribution']}",
        "",
        "## Risk-Adjusted Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Annualized Sharpe ratio | {risk['sharpe_ratio']} |",
        f"| Annualized Sortino ratio | {risk['sortino_ratio']} |",
        f"| Max drawdown | {risk['max_drawdown_pct']:.2f}% |",
        f"| Daily-return samples | {risk['daily_return_samples']} |",
        "",
    ]
    return "\n".join(lines)


async def main():
    num_cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 3

    print("\n" + "=" * 70)
    print(f"📊 Generating statistical results over {num_cycles} workflow cycle(s)".center(70))
    print("=" * 70 + "\n")

    await init_db()
    supervisor = SupervisorAgent()

    async with async_session() as session:
        await supervisor.seed_cities(session)
        for i in range(num_cycles):
            logging.getLogger("stats").info(f"Running workflow cycle {i + 1}/{num_cycles}...")
            result = await supervisor.run_workflow(session)
            logging.getLogger("stats").info(
                f"Cycle {i + 1} done — trades: {result['trades_executed']}, "
                f"value: ${result['portfolio_value']:.2f}"
            )

        report = await collect_statistics(session)

    RESULTS_DIR.mkdir(exist_ok=True)
    json_path = RESULTS_DIR / "statistical_results.json"
    md_path = RESULTS_DIR / "statistical_results.md"
    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(render_markdown(report))

    print(render_markdown(report))
    print(f"\n✅ Saved: {json_path}")
    print(f"✅ Saved: {md_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
