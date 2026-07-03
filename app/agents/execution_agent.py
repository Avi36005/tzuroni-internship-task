import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.base import BaseAgent
from app.paper_trader.trader import PaperTrader
from app.database.models import Market, Order

logger = logging.getLogger(__name__)

class ExecutionAgent(BaseAgent):
    """
    Agent 7: Execution Agent.
    Interacts with the PaperTrader engine to execute paper trades, record transaction slippage,
    and update positions in the database.
    """
    
    SYSTEM_PROMPT = (
        "You are the Execution Agent. Your job is to execute trades cleanly in the simulated paper trading environment, "
        "measure execution slippage, verify portfolio balances, and format detailed order logs."
    )

    def __init__(self, paper_trader: Optional[PaperTrader] = None):
        super().__init__(name="ExecutionAgent", system_prompt=self.SYSTEM_PROMPT)
        self.trader = paper_trader or PaperTrader()

    async def execute_trade(
        self,
        session: AsyncSession,
        market: Market,
        side: str,
        cost_dollars: float,
        reason: str
    ) -> Dict[str, Any]:
        """Execute paper trade and log outputs"""
        logger.info(f"ExecutionAgent: Initiating trade for market: {market.slug}, Side: {side}, Cost: ${cost_dollars:.2f}")
        
        # Call PaperTrader order execution
        order = await self.trader.place_order(
            session=session,
            market=market,
            side=side,
            cost_dollars=cost_dollars,
            reason=reason
        )
        
        if not order:
            logger.error("ExecutionAgent: Trade execution failed.")
            return {
                "success": False,
                "message": "Execution engine failed to process trade."
            }
            
        # Write LLM execution report
        prompt = (
            f"Write a short, professional execution log for this transaction:\n"
            f"- Market Title: {market.title}\n"
            f"- Side Executed: {side}\n"
            f"- Allocated Cost: ${cost_dollars:.2f}\n"
            f"- Execution Price: {order.price:.2f}\n"
            f"- Shares Acquired: {order.amount:.2f}\n"
            f"- Slippage Incurred: {order.slippage:.2%}\n"
            f"- Order Reason: {reason}\n"
        )
        
        execution_report = await self.chat(prompt)
        
        return {
            "success": True,
            "order_id": order.id,
            "shares": order.amount,
            "execution_price": order.price,
            "slippage": order.slippage,
            "report": execution_report
        }
