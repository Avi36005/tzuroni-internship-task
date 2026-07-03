import asyncio
import logging
from sqlalchemy import select
from app.database.db import init_db, async_session
from app.database.models import PortfolioState, Position, Market, Prediction, Order, City
from app.agents.supervisor import SupervisorAgent

# Set up logging for CLI execution
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
# Reduce verbose logging from third party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

async def main():
    print("\n" + "="*70)
    print("🚀 Starting Weather Prediction AI Trading Agent Demo".center(70))
    print("="*70 + "\n")
    
    # 1. Initialize DB and seed cities
    logger = logging.getLogger("demo")
    logger.info("Initializing database and seeding support for 20 cities...")
    await init_db()
    
    async with async_session() as session:
        supervisor = SupervisorAgent()
        await supervisor.seed_cities(session)
        
        # 2. Run supervisor agent workflow cycle
        logger.info("Starting supervisor workflow orchestration...")
        result = await supervisor.run_workflow(session)
        logger.info("Supervisor workflow cycle completed.")
        
        # 3. Print out results
        print("\n" + "="*70)
        print("📊 DEMO EXECUTION SUMMARY".center(70))
        print("="*70)
        print(f"  Workflow Success:      {result['success']}")
        print(f"  Trades Executed:       {result['trades_executed']}")
        print(f"  Hedges Executed:       {result['hedges_executed']}")
        print(f"  Final Portfolio Value: ${result['portfolio_value']:.2f}")
        print(f"  Available Cash:        ${result['cash']:.2f}")
        
        # 4. Fetch and display open positions
        pos_stmt = select(Position)
        pos_res = await session.execute(pos_stmt)
        positions = pos_res.scalars().all()
        
        print("\n" + "-"*70)
        print(f"💼 ACTIVE PORTFOLIO HOLDINGS ({len(positions)})".center(70))
        print("-"*70)
        if positions:
            for pos in positions:
                m_stmt = select(Market).where(Market.id == pos.market_id)
                m_res = await session.execute(m_stmt)
                market = m_res.scalar_one()
                print(
                    f"  {market.title[:30]:<30} | Side: {pos.side:<3} | "
                    f"Shares: {pos.shares:7.2f} | Avg: ${pos.average_price:.2f} | "
                    f"Current: ${pos.current_price:.2f} | PnL: ${pos.pnl:+6.2f}"
                )
        else:
            print("  No open positions.")
            
        # 5. Fetch and display predictions
        pred_stmt = select(Prediction).order_by(Prediction.created_at.desc()).limit(5)
        pred_res = await session.execute(pred_stmt)
        preds = pred_res.scalars().all()
        
        print("\n" + "-"*70)
        print("🔮 RECENT PREDICTIONS (Top 5)".center(70))
        print("-"*70)
        if preds:
            for p in preds:
                m_stmt = select(Market).where(Market.id == p.market_id)
                m_res = await session.execute(m_stmt)
                market = m_res.scalar_one()
                print(
                    f"  {market.title[:25]:<25} | Model Prob: {p.model_probability_yes:5.1%} | "
                    f"Mkt Price: ${market.yes_price:.2f} | Edge: {p.edge:+5.1%} | "
                    f"EV: ${p.expected_value:+.2f} | Decision: {p.decision}"
                )
        else:
            print("  No predictions recorded.")
            
        # 6. Fetch and display orders
        order_stmt = select(Order).order_by(Order.executed_at.desc()).limit(5)
        order_res = await session.execute(order_stmt)
        orders = order_res.scalars().all()
        
        print("\n" + "-"*70)
        print("📜 RECENT ORDER EXECUTION AUDIT (Top 5)".center(70))
        print("-"*70)
        if orders:
            for o in orders:
                m_stmt = select(Market).where(Market.id == o.market_id)
                m_res = await session.execute(m_stmt)
                market = m_res.scalar_one()
                print(
                    f"  {market.title[:25]:<25} | Side: {o.side:<3} | "
                    f"Shares: {o.amount:7.2f} | Price: ${o.price:.2f} | "
                    f"Cost: ${o.cost:7.2f} | Slippage: {o.slippage:5.2%}"
                )
        else:
            print("  No orders executed.")
            
    print("\n" + "="*70)
    print("Demo Execution Completed Successfully!".center(70))
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
