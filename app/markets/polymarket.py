import json
import logging
import random
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.config.settings import settings
from app.weather.client import OpenMeteoClient

logger = logging.getLogger(__name__)

# Keywords used to identify weather-related markets in the live Polymarket feed.
_WEATHER_KEYWORDS = ("weather", "rain", "temperature", "snow", "degrees", "°", "hottest", "warmest")


class PolymarketClient:
    """
    Client for interacting with Polymarket weather markets.

    Fetches real markets from the Polymarket Gamma API. Polymarket geoblocks several
    regions; set POLYMARKET_PROXY (a VPN/HTTP proxy URL) to reach the real API from a
    blocked location. When the real API is unreachable:
      - if ALLOW_SIMULATED_MARKETS is True (default), a forecast-anchored simulator is
        used so paper trading can still be demonstrated (markets tagged is_simulated=True);
      - if False, no markets are returned (strict real-data-only mode).
    """

    GAMMA_URL = "https://gamma-api.polymarket.com"

    def __init__(self, client: Optional[httpx.AsyncClient] = None, open_meteo: Optional[OpenMeteoClient] = None):
        proxy = settings.polymarket_proxy or None
        self.client = client or httpx.AsyncClient(timeout=15.0, proxy=proxy, follow_redirects=True)
        self.open_meteo = open_meteo or OpenMeteoClient()
        self.is_simulated = False

    async def get_active_markets(self, cities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch real active weather markets from Polymarket, honouring the real-only policy."""
        real_markets = await self._fetch_live_markets()
        if real_markets is not None:
            self.is_simulated = False
            logger.info(f"Loaded {len(real_markets)} live Polymarket weather markets.")
            return real_markets

        # Real API unreachable.
        if not settings.allow_simulated_markets:
            logger.warning(
                "Polymarket unreachable and ALLOW_SIMULATED_MARKETS=false: "
                "returning no markets (strict real-data-only mode)."
            )
            self.is_simulated = False
            return []

        logger.warning(
            "Polymarket API unreachable (region likely geoblocked). Using forecast-anchored "
            "simulator; markets are tagged is_simulated=True. Set POLYMARKET_PROXY to use real data."
        )
        self.is_simulated = True
        return await self._generate_simulated_markets(cities)

    async def _fetch_live_markets(self) -> Optional[List[Dict[str, Any]]]:
        """
        Query the Gamma API for real active weather markets.
        Returns a list on success (possibly empty), or None if the API is unreachable.
        """
        try:
            logger.info("Fetching active weather markets from Polymarket Gamma API")
            response = await self.client.get(
                f"{self.GAMMA_URL}/markets",
                params={"active": "true", "closed": "false", "limit": 500},
            )
            if response.status_code != 200:
                logger.warning(f"Polymarket Gamma API returned status {response.status_code}.")
                return None

            data = response.json()
            records = data if isinstance(data, list) else data.get("data", [])
            markets = []
            for m in records:
                title = (m.get("question") or m.get("title") or "")
                if not any(kw in title.lower() for kw in _WEATHER_KEYWORDS):
                    continue

                prices = self._as_list(m.get("outcomePrices"))
                tokens = self._as_list(m.get("clobTokenIds"))
                yes_price = float(prices[0]) if len(prices) > 0 else 0.5
                no_price = float(prices[1]) if len(prices) > 1 else round(1.0 - yes_price, 4)

                markets.append({
                    "title": title,
                    "slug": m.get("slug"),
                    "condition_id": m.get("conditionId"),
                    "clob_token_id_yes": tokens[0] if len(tokens) > 0 else None,
                    "clob_token_id_no": tokens[1] if len(tokens) > 1 else None,
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "implied_probability": yes_price,
                    "volume": float(m.get("volume") or 0.0),
                    "liquidity": float(m.get("liquidity") or 0.0),
                    "spread": float(m.get("spread") or max(0.01, abs(1.0 - (yes_price + no_price)))),
                    "expiration_date": (m.get("endDate") or "")[:10] or
                        (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
                    "is_active": True,
                    "is_simulated": False,
                })
            return markets
        except Exception as e:
            logger.warning(f"Could not reach Polymarket API (likely geoblocked): {e}")
            return None

    @staticmethod
    def _as_list(value: Any) -> List[Any]:
        """Gamma returns outcomePrices / clobTokenIds as JSON-encoded strings or arrays."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                return []
        return []

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
                "is_active": True,
                "is_simulated": True
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
                "is_active": True,
                "is_simulated": True
            })

        return markets
