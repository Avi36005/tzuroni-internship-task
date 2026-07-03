import logging
import random
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.config.settings import settings
from app.weather.client import OpenMeteoClient

logger = logging.getLogger(__name__)

class PolymarketClient:
    """
    Client for interacting with Polymarket weather markets.
    Supports a live client that falls back to a high-fidelity simulator when geoblocked.
    """
    
    GAMMA_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self, client: Optional[httpx.AsyncClient] = None, open_meteo: Optional[OpenMeteoClient] = None):
        self.client = client or httpx.AsyncClient(timeout=10.0)
        self.open_meteo = open_meteo or OpenMeteoClient(self.client)
        self.is_simulated = False

    async def get_active_markets(self, cities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fetch active weather markets from Polymarket.
        If geoblocked or API call fails, switch to Simulation Mode using live weather forecasts.
        """
        if self.is_simulated:
            return await self._generate_simulated_markets(cities)
            
        try:
            logger.info("Attempting to fetch active weather markets from Polymarket Gamma API")
            # Query Gamma API public-search for weather markets
            response = await self.client.get(
                f"{self.GAMMA_URL}/public-search", 
                params={"q": "weather", "active": "true"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if len(data) > 0:
                    markets = []
                    for m in data:
                        # Extract and format matching Polymarket schema
                        outcomes = m.get("outcomes", ["YES", "NO"])
                        prices = m.get("outcomePrices", ["0.5", "0.5"])
                        
                        yes_price = float(prices[0]) if len(prices) > 0 else 0.5
                        no_price = float(prices[1]) if len(prices) > 1 else 0.5
                        
                        markets.append({
                            "title": m.get("title"),
                            "slug": m.get("slug"),
                            "condition_id": m.get("conditionId"),
                            "clob_token_id_yes": m.get("clobTokenIds", [None])[0] if m.get("clobTokenIds") else None,
                            "clob_token_id_no": m.get("clobTokenIds", [None, None])[1] if m.get("clobTokenIds") and len(m.get("clobTokenIds")) > 1 else None,
                            "yes_price": yes_price,
                            "no_price": no_price,
                            "implied_probability": yes_price,
                            "volume": float(m.get("volume", 1000.0)),
                            "liquidity": float(m.get("liquidity", 500.0)),
                            "spread": max(0.01, abs(1.0 - (yes_price + no_price))),
                            "expiration_date": m.get("endDate", (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d")),
                            "is_active": True
                        })
                    logger.info(f"Successfully loaded {len(markets)} live Polymarket markets.")
                    return markets
            
            # If not 200, trigger simulated fallback
            logger.warning(f"Polymarket API returned status code {response.status_code}. Activating Simulation Mode.")
            self.is_simulated = True
            return await self._generate_simulated_markets(cities)
            
        except Exception as e:
            logger.warning(f"Failed to connect to Polymarket API (likely geoblocked): {e}. Activating Simulation Mode.")
            self.is_simulated = True
            return await self._generate_simulated_markets(cities)

    async def _generate_simulated_markets(self, cities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate high-fidelity simulated weather markets linked to actual forecast data.
        This provides a realistic trading simulator for paper trades when geoblocked.
        """
        logger.info("Generating simulated weather markets based on actual daily weather forecasts.")
        markets = []
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        for city in cities:
            city_id = city["id"]
            city_name = city["name"]
            lat = city["latitude"]
            lon = city["longitude"]
            
            # Fetch forecast to anchor simulated odds
            forecast = await self.open_meteo.get_forecast(lat, lon)
            
            # 1. Rain Market Simulation
            rain_prob = 30.0  # default prior
            if forecast and "daily" in forecast and "precipitation_probability_max" in forecast["daily"]:
                probs = forecast["daily"]["precipitation_probability_max"]
                if len(probs) > 1:
                    rain_prob = float(probs[1])  # Index 1 is tomorrow
            
            # Add market-maker noise (odds lag, noise, spreads)
            noise = random.uniform(-0.08, 0.08)
            yes_price = min(0.98, max(0.02, (rain_prob / 100.0) + noise))
            no_price = 1.0 - yes_price
            spread = random.uniform(0.01, 0.03)
            
            # Bid/Ask spread adjustments
            yes_price = round(yes_price, 2)
            no_price = round(no_price, 2)
            
            markets.append({
                "city_id": city_id,
                "title": f"Will it rain in {city_name} tomorrow ({tomorrow})?",
                "slug": f"will-it-rain-in-{city_name.lower().replace(' ', '-')}-{tomorrow}",
                "condition_id": f"cond_rain_{city_name.lower()[:3]}_{tomorrow.replace('-', '')}",
                "clob_token_id_yes": f"tok_yes_rain_{city_name.lower()[:3]}_{tomorrow.replace('-', '')}",
                "clob_token_id_no": f"tok_no_rain_{city_name.lower()[:3]}_{tomorrow.replace('-', '')}",
                "yes_price": yes_price,
                "no_price": no_price,
                "implied_probability": yes_price,
                "volume": round(random.uniform(5000.0, 50000.0), 2),
                "liquidity": round(random.uniform(2000.0, 15000.0), 2),
                "spread": round(spread, 3),
                "expiration_date": tomorrow,
                "is_active": True
            })
            
            # 2. Temperature Market Simulation (e.g. will exceed 30°C/86°F or historical average)
            temp_max = 22.0  # default prior
            if forecast and "daily" in forecast and "temperature_2m_max" in forecast["daily"]:
                temps = forecast["daily"]["temperature_2m_max"]
                if len(temps) > 1:
                    temp_max = float(temps[1])
                    
            threshold = 30.0 if temp_max < 30.0 else 35.0
            if temp_max < 20.0:
                threshold = 25.0
                
            # Odds of exceeding threshold
            temp_prob = 10.0 if temp_max < threshold - 3 else (90.0 if temp_max > threshold + 1 else 50.0)
            noise = random.uniform(-0.10, 0.10)
            yes_price_t = min(0.97, max(0.03, (temp_prob / 100.0) + noise))
            no_price_t = 1.0 - yes_price_t
            
            yes_price_t = round(yes_price_t, 2)
            no_price_t = round(no_price_t, 2)
            
            markets.append({
                "city_id": city_id,
                "title": f"Will the temperature in {city_name} exceed {threshold}°C tomorrow ({tomorrow})?",
                "slug": f"will-temp-exceed-{threshold}-in-{city_name.lower().replace(' ', '-')}-{tomorrow}",
                "condition_id": f"cond_temp_{city_name.lower()[:3]}_{tomorrow.replace('-', '')}",
                "clob_token_id_yes": f"tok_yes_temp_{city_name.lower()[:3]}_{tomorrow.replace('-', '')}",
                "clob_token_id_no": f"tok_no_temp_{city_name.lower()[:3]}_{tomorrow.replace('-', '')}",
                "yes_price": yes_price_t,
                "no_price": no_price_t,
                "implied_probability": yes_price_t,
                "volume": round(random.uniform(3000.0, 30000.0), 2),
                "liquidity": round(random.uniform(1000.0, 10000.0), 2),
                "spread": round(random.uniform(0.01, 0.04), 3),
                "expiration_date": tomorrow,
                "is_active": True
            })
            
        return markets
