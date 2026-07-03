import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import init_db, async_session, get_db_context
from app.database.models import City, Market, Prediction, Order, Position, PortfolioState
from app.agents.supervisor import SupervisorAgent
from app.portfolio.manager import PortfolioManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

supervisor = SupervisorAgent()
portfolio_manager = PortfolioManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and seed default cities
    logger.info("Initializing database...")
    await init_db()
    async with async_session() as session:
        await supervisor.seed_cities(session)
    logger.info("Database initialized successfully.")
    yield

app = FastAPI(
    title="Weather Prediction AI Trading Agent API",
    description="Backend API for quantitative weather-market prediction, risk analysis, and paper trading execution.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_db_session():
    async with async_session() as session:
        yield session

@app.post("/run-workflow")
async def trigger_workflow(session: AsyncSession = Depends(get_db_session)):
    """Manually trigger one complete multi-agent prediction & trading cycle"""
    try:
        result = await supervisor.run_workflow(session)
        return result
    except Exception as e:
        logger.error(f"Error running workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/portfolio/state")
async def get_portfolio_state(session: AsyncSession = Depends(get_db_session)):
    """Fetch the latest portfolio cash, exposure, and revalued equity state"""
    stmt = select(PortfolioState).order_by(PortfolioState.timestamp.desc()).limit(1)
    result = await session.execute(stmt)
    state = result.scalar_one_or_none()
    
    if not state:
        # Initial default state
        return {
            "cash": 10000.0,
            "portfolio_value": 10000.0,
            "unrealized_pnl": 0.0,
            "daily_return": 0.0,
            "exposure": 0.0,
            "max_drawdown": 0.0,
            "timestamp": None
        }
        
    return {
        "cash": state.cash,
        "portfolio_value": state.portfolio_value,
        "unrealized_pnl": state.unrealized_pnl,
        "daily_return": state.daily_return,
        "exposure": state.exposure,
        "max_drawdown": state.max_drawdown,
        "timestamp": state.timestamp
    }

@app.get("/portfolio/history")
async def get_portfolio_history(session: AsyncSession = Depends(get_db_session)):
    """Fetch the historical equity curve data for charting"""
    stmt = select(PortfolioState).order_by(PortfolioState.timestamp.asc())
    result = await session.execute(stmt)
    states = result.scalars().all()
    
    return [
        {
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            "portfolio_value": s.portfolio_value,
            "cash": s.cash,
            "exposure": s.exposure,
            "unrealized_pnl": s.unrealized_pnl
        }
        for s in states
    ]

@app.get("/portfolio/statistics")
async def get_portfolio_stats(session: AsyncSession = Depends(get_db_session)):
    """Calculate and return Sharpe, Sortino, Win Rate, and Drawdown statistics"""
    stats = await portfolio_manager.calculate_portfolio_statistics(session)
    return stats

@app.get("/positions")
async def get_active_positions(session: AsyncSession = Depends(get_db_session)):
    """Fetch all open paper trading positions"""
    stmt = select(Position)
    result = await session.execute(stmt)
    positions = result.scalars().all()
    
    output = []
    for p in positions:
        m_stmt = select(Market).where(Market.id == p.market_id)
        m_res = await session.execute(m_stmt)
        market = m_res.scalar_one_or_none()
        
        c_name = "Unknown"
        if market:
            c_stmt = select(City).where(City.id == market.city_id)
            c_res = await session.execute(c_stmt)
            city = c_res.scalar_one_or_none()
            if city:
                c_name = city.name
                
        output.append({
            "id": p.id,
            "market_slug": market.slug if market else "unknown",
            "market_title": market.title if market else "unknown",
            "city_name": c_name,
            "side": p.side,
            "shares": p.shares,
            "average_price": p.average_price,
            "current_price": p.current_price,
            "pnl": p.pnl,
            "is_hedged": p.is_hedged
        })
    return output

@app.get("/trades")
async def get_trade_history(session: AsyncSession = Depends(get_db_session)):
    """Fetch order execution history logs"""
    stmt = select(Order).order_by(Order.executed_at.desc())
    result = await session.execute(stmt)
    orders = result.scalars().all()
    
    output = []
    for o in orders:
        m_stmt = select(Market).where(Market.id == o.market_id)
        m_res = await session.execute(m_stmt)
        market = m_res.scalar_one_or_none()
        
        output.append({
            "id": o.id,
            "market_slug": market.slug if market else "unknown",
            "market_title": market.title if market else "unknown",
            "side": o.side,
            "price": o.price,
            "amount": o.amount,
            "cost": o.cost,
            "reason": o.reason,
            "status": o.status,
            "slippage": o.slippage,
            "executed_at": o.executed_at
        })
    return output

@app.get("/predictions")
async def get_predictions(session: AsyncSession = Depends(get_db_session)):
    """Fetch prediction details generated by Prediction Agent"""
    stmt = select(Prediction).order_by(Prediction.created_at.desc())
    result = await session.execute(stmt)
    preds = result.scalars().all()
    
    output = []
    for p in preds:
        m_stmt = select(Market).where(Market.id == p.market_id)
        m_res = await session.execute(m_stmt)
        market = m_res.scalar_one_or_none()
        
        output.append({
            "id": p.id,
            "market_title": market.title if market else "unknown",
            "prediction_date": p.prediction_date,
            "probability_yes": p.model_probability_yes,
            "probability_no": p.model_probability_no,
            "confidence": p.confidence,
            "edge": p.edge,
            "expected_value": p.expected_value,
            "decision": p.decision,
            "reasoning": p.reasoning,
            "created_at": p.created_at
        })
    return output

@app.get("/cities")
async def get_supported_cities(session: AsyncSession = Depends(get_db_session)):
    """Fetch the list of 20 supported cities with their agencies and coordinates"""
    stmt = select(City)
    result = await session.execute(stmt)
    cities = result.scalars().all()
    return cities

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
