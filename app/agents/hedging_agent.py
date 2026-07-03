import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.base import BaseAgent
from app.hedging.hedger import HedgingEngine
from app.database.models import Position, Market

logger = logging.getLogger(__name__)

class HedgingAgent(BaseAgent):
    """
    Agent 9: Hedging Agent.
    Monitors portfolio risk concentrations, identifies high-exposure cities, and executes
    offsetting weather correlation hedges for capital protection.
    """
    
    SYSTEM_PROMPT = (
        "You are the Hedging Agent. Your job is to act as a Capital Protection Engine. "
        "You analyze position risk concentration, look for geographical weather correlations, "
        "and calculate hedging transactions (YES vs NO offsets or cross-city correlation hedges) "
        "to reduce the portfolio's net beta exposure. Keep your summaries highly risk-focused."
    )

    def __init__(self, hedging_engine: Optional[HedgingEngine] = None):
        super().__init__(name="HedgingAgent", system_prompt=self.SYSTEM_PROMPT)
        self.engine = hedging_engine or HedgingEngine()

    async def check_hedges(
        self,
        session: AsyncSession,
        active_positions: List[Dict[str, Any]],
        available_markets: List[Dict[str, Any]],
        portfolio_value: float
    ) -> List[Dict[str, Any]]:
        """Scan open positions and recommend hedging trades"""
        logger.info("HedgingAgent: Scanning open positions for hedging requirements...")
        
        # Calculate recommendations using hedging engine
        hedges = self.engine.calculate_hedges(
            active_positions=active_positions,
            available_markets=available_markets,
            portfolio_value=portfolio_value
        )
        
        if not hedges:
            return []
            
        # Format recommendations for LLM summary
        hedge_details = ""
        for i, h in enumerate(hedges):
            hedge_details += (
                f"Hedge {i+1}: Market slug: {h['slug']}\n"
                f"  Side: {h['side']}\n"
                f"  Price: {h['price']}\n"
                f"  Target Allocation Cost: ${h['cost']:.2f}\n"
                f"  Hedge Reason: {h['reason']}\n\n"
            )
            
        prompt = (
            f"Review the recommended hedging trades to protect our portfolio (Value: ${portfolio_value:.2f}):\n\n"
            f"{hedge_details}"
            "Provide a concise capital protection statement. Explain how these hedges reduce volatility and protect tail risk."
        )
        
        hedging_analysis = await self.chat(prompt)
        
        # Annotate recommendations with analysis report
        for h in hedges:
            h["analysis"] = hedging_analysis
            
        return hedges
