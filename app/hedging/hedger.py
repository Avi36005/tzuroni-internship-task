import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Weather correlation matrix for our supported cities (1.0 = perfect positive correlation, -1.0 = perfect negative)
WEATHER_CORRELATIONS = {
    ("New York", "Chicago"): 0.55,
    ("New York", "Toronto"): 0.50,
    ("London", "Paris"): 0.70,
    ("London", "Amsterdam"): 0.75,
    ("Paris", "Amsterdam"): 0.80,
    ("Paris", "Berlin"): 0.60,
    ("Berlin", "Amsterdam"): 0.65,
    ("Mumbai", "Delhi"): 0.45,
    ("Sydney", "Melbourne"): 0.50,
    ("Singapore", "Bangkok"): 0.40,
    ("Rome", "Madrid"): 0.60,
}

class HedgingEngine:
    """
    Hedging Engine for quantitative capital protection.
    Calculates offsetting trades based on contract spreads, YES/NO offsets, and city-weather correlations.
    """
    
    def __init__(self, hedge_threshold: float = 0.05):
        self.hedge_threshold = hedge_threshold  # Trigger hedge if city exposure > 5% of portfolio

    def get_correlation(self, city_a: str, city_b: str) -> float:
        """Retrieve correlation coefficient between two cities"""
        if city_a == city_b:
            return 1.0
        return (
            WEATHER_CORRELATIONS.get((city_a, city_b)) or 
            WEATHER_CORRELATIONS.get((city_b, city_a)) or 
            0.0
        )

    def calculate_hedges(
        self,
        active_positions: List[Dict[str, Any]],
        available_markets: List[Dict[str, Any]],
        portfolio_value: float
    ) -> List[Dict[str, Any]]:
        """
        Scan open positions and generate recommended hedging orders.
        Methods:
        1. YES vs NO: If prediction changes, offset by trading the opposite side.
        2. Cross-City correlation hedge: Offset high-exposure cities using correlated markets.
        """
        hedges = []
        
        # Calculate exposure per city
        city_exposures = {}
        for pos in active_positions:
            city_name = pos.get("city_name")
            exposure = pos.get("shares", 0.0) * pos.get("current_price", 0.0)
            city_exposures[city_name] = city_exposures.get(city_name, 0.0) + exposure
            
        for city_name, exposure in city_exposures.items():
            exposure_pct = exposure / portfolio_value if portfolio_value > 0 else 0.0
            
            # Check if exposure exceeds threshold
            if exposure_pct < self.hedge_threshold:
                continue
                
            logger.info(f"High exposure detected in {city_name} ({exposure_pct:.1%}). Scanning for hedges...")
            
            # Look for correlated cities in available markets
            for market in available_markets:
                m_city_name = market.get("city_name")
                if m_city_name == city_name or m_city_name not in city_exposures:
                    corr = self.get_correlation(city_name, m_city_name)
                    
                    if corr >= 0.50:  # Strong positive correlation
                        # To hedge a Long position in a positively correlated city, we sell or buy NO in the other city
                        # Let's say we are long YES in City A. We can buy NO in City B.
                        pos_side = [p.get("side") for p in active_positions if p.get("city_name") == city_name][0]
                        hedge_side = "NO" if pos_side == "YES" else "YES"
                        
                        # Calculate hedge size (typically proportional to correlation and exposure)
                        hedge_ratio = corr * 0.5  # hedge 50% of the correlated risk
                        hedge_cost = exposure * hedge_ratio
                        
                        # Verify we don't already have a position in this market
                        already_positioned = any(p.get("market_id") == market["id"] for p in active_positions)
                        if not already_positioned:
                            logger.info(f"Recommended cross-city hedge: Buy {hedge_side} in {m_city_name} to offset {city_name} risk (Correlation: {corr:.2f})")
                            hedges.append({
                                "market_id": market["id"],
                                "slug": market["slug"],
                                "side": hedge_side,
                                "price": market["yes_price"] if hedge_side == "YES" else market["no_price"],
                                "cost": hedge_cost,
                                "reason": f"Cross-city correlation hedge for {city_name} exposure. Correlation: {corr:.2f}"
                            })
                            
        return hedges
