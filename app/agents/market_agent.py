import logging
from typing import Dict, Any, List, Optional
from app.agents.base import BaseAgent
from app.markets.polymarket import PolymarketClient

logger = logging.getLogger(__name__)

class MarketAgent(BaseAgent):
    """
    Agent 3: Market Agent.
    Interacts with Polymarket Client. Collects active weather contracts,
    YES/NO prices, volume, liquidity, spreads, and calculates market implied probabilities.
    """
    
    SYSTEM_PROMPT = (
        "You are the Market Agent. Your job is to analyze prediction market order books, "
        "YES/NO share prices, spreads, volume, and liquidity. You calculate market implied probability "
        "and identify discrepancies between odds and fundamentals. Keep your assessments highly financial."
    )

    def __init__(self, polymarket_client: Optional[PolymarketClient] = None):
        super().__init__(name="MarketAgent", system_prompt=self.SYSTEM_PROMPT)
        self.polymarket = polymarket_client or PolymarketClient()

    async def analyze_markets(self, city_id: int, city_name: str, available_markets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Filter markets for a city and return financial summaries"""
        # Filter available markets for the target city
        city_markets = [m for m in available_markets if m.get("city_id") == city_id or city_name.lower() in m.get("title", "").lower()]
        
        if not city_markets:
            logger.info(f"MarketAgent: No active weather markets found for {city_name}.")
            return {
                "success": False,
                "summary": f"No active weather markets found for {city_name}.",
                "markets": []
            }
            
        # Format prompt with market data for LLM analysis
        market_details = ""
        for i, m in enumerate(city_markets):
            market_details += (
                f"Market {i+1}: {m['title']}\n"
                f"  YES Price: ${m['yes_price']:.2f} (Implied Prob: {m['yes_price']:.1%})\n"
                f"  NO Price: ${m['no_price']:.2f}\n"
                f"  Volume: ${m['volume']:.2f}\n"
                f"  Liquidity: ${m['liquidity']:.2f}\n"
                f"  Spread: ${m['spread']:.3f}\n\n"
            )
            
        prompt = (
            f"Analyze the following active Polymarket contracts for {city_name}:\n\n"
            f"{market_details}"
            "Summarize the market sentiment. Identify if any contracts are thinly traded (low liquidity or wide spreads) "
            "and note the implied market probability of the weather outcomes."
        )
        
        analysis = await self.chat(prompt)
        
        return {
            "success": True,
            "summary": analysis,
            "markets": city_markets
        }
