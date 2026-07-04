import logging
from datetime import datetime, timedelta
import httpx
from typing import Dict, Any, List, Optional
from app.config.settings import settings

logger = logging.getLogger(__name__)

class OpenMeteoClient:
    """Async client for Open-Meteo APIs (Global Forecast and Historical Archive)"""
    
    BASE_URL = "https://api.open-meteo.com/v1"
    ARCHIVE_URL = "https://archive-api.open-meteo.com/v1"
    
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client or httpx.AsyncClient(timeout=15.0)

    async def get_forecast(self, lat: float, lon: float, timezone: str = "auto") -> Optional[Dict[str, Any]]:
        """Fetch 10-day weather forecast including precipitation probabilities and temperature ranges"""
        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": [
                "temperature_2m_max", 
                "temperature_2m_min", 
                "precipitation_sum", 
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "relative_humidity_2m_max",
                "surface_pressure_mean"
            ],
            "timezone": timezone
        }
        
        try:
            logger.info(f"Fetching Open-Meteo forecast for {lat}, {lon}")
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Open-Meteo API returned status code {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error fetching Open-Meteo forecast: {e}", exc_info=True)
            return None

    async def get_historical_climatology(
        self, lat: float, lon: float, start_date: str, end_date: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch historical daily precipitation and temperature for climatological baseline"""
        url = f"{self.ARCHIVE_URL}/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": ["precipitation_sum", "temperature_2m_max", "temperature_2m_min"],
            "timezone": "auto"
        }
        
        try:
            logger.info(f"Fetching Open-Meteo archive for {lat}, {lon} from {start_date} to {end_date}")
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Open-Meteo Archive API returned status code {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error fetching Open-Meteo archive: {e}", exc_info=True)
            return None


class NOAAClient:
    """Async client for NOAA (US National Weather Service) API"""
    
    BASE_URL = "https://api.weather.gov"
    HEADERS = {
        "User-Agent": "WeatherAI-TradingAgent/1.0 (contact@weatheraitrading.com)",
        "Accept": "application/ld+json"
    }

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client or httpx.AsyncClient(timeout=15.0, headers=self.HEADERS)

    async def get_gridpoint_forecast(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Fetch NOAA forecast by first resolving points metadata to retrieve the grid forecast URL"""
        point_url = f"{self.BASE_URL}/points/{lat:.4f},{lon:.4f}"
        
        try:
            logger.info(f"Fetching NOAA points metadata for {lat}, {lon}")
            point_resp = await self.client.get(point_url)
            if point_resp.status_code != 200:
                logger.error(f"NOAA points lookup failed for {lat}, {lon}: {point_resp.status_code}")
                return None
                
            point_data = point_resp.json()
            # If the format is JSON-LD, properties is typically flat or nested
            properties = point_data.get("properties", {}) or point_data
            forecast_url = properties.get("forecast")
            
            if not forecast_url:
                logger.error("NOAA forecast URL not found in points metadata")
                return None
                
            logger.info(f"Fetching NOAA forecast from {forecast_url}")
            forecast_resp = await self.client.get(forecast_url)
            if forecast_resp.status_code == 200:
                return forecast_resp.json()
            else:
                logger.error(f"NOAA forecast fetch failed: {forecast_resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching NOAA gridpoint forecast: {e}", exc_info=True)
            return None

    async def get_alerts_for_coords(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        """Fetch active weather alerts for a set of coordinates"""
        url = f"{self.BASE_URL}/alerts/active"
        params = {"point": f"{lat:.4f},{lon:.4f}"}
        
        try:
            logger.info(f"Fetching NOAA active alerts for {lat}, {lon}")
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                features = data.get("features", []) or data.get("@graph", []) or []
                alerts = []
                for f in features:
                    props = f.get("properties", {}) or f
                    alerts.append({
                        "event": props.get("event"),
                        "severity": props.get("severity"),
                        "urgency": props.get("urgency"),
                        "headline": props.get("headline"),
                        "description": props.get("description")
                    })
                return alerts
            else:
                logger.error(f"NOAA alerts lookup failed: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching NOAA alerts: {e}", exc_info=True)
            return []


class MetNoClient:
    """
    Async client for the Norwegian Meteorological Institute (MET Norway / api.met.no).

    MET Norway is an official national meteorological service that publishes global,
    coordinate-based forecasts with no API key required. It is used here as an official
    "local source" for cities outside the US (which are covered by NOAA), fulfilling the
    requirement to fetch local per-country weather from local government sources.
    """

    BASE_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
    HEADERS = {
        "User-Agent": "WeatherAI-TradingAgent/1.0 (contact@weatheraitrading.com)",
        "Accept": "application/json",
    }

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client or httpx.AsyncClient(timeout=15.0, headers=self.HEADERS)

    async def get_forecast(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Fetch and summarise the official MET Norway forecast for the next 24 hours."""
        params = {"lat": f"{lat:.4f}", "lon": f"{lon:.4f}"}
        try:
            logger.info(f"Fetching MET Norway forecast for {lat}, {lon}")
            response = await self.client.get(self.BASE_URL, params=params)
            if response.status_code != 200:
                logger.error(f"MET Norway API returned status code {response.status_code}")
                return None

            data = response.json()
            timeseries = data.get("properties", {}).get("timeseries", [])
            if not timeseries:
                return None

            # Aggregate the next 24 hourly entries into a daily summary.
            horizon = timeseries[:24]
            temps: List[float] = []
            total_precip = 0.0
            max_precip_prob = 0.0
            symbols: List[str] = []

            for entry in horizon:
                details = entry.get("data", {}).get("instant", {}).get("details", {})
                if "air_temperature" in details:
                    temps.append(details["air_temperature"])

                next_hour = entry.get("data", {}).get("next_1_hours", {})
                if next_hour:
                    total_precip += next_hour.get("details", {}).get("precipitation_amount", 0.0) or 0.0
                    prob = next_hour.get("details", {}).get("probability_of_precipitation")
                    if prob is not None:
                        max_precip_prob = max(max_precip_prob, prob)
                    symbol = next_hour.get("summary", {}).get("symbol_code")
                    if symbol:
                        symbols.append(symbol)

            dominant_symbol = max(set(symbols), key=symbols.count) if symbols else "unknown"
            return {
                "source": "MET Norway (api.met.no)",
                "temp_max": max(temps) if temps else None,
                "temp_min": min(temps) if temps else None,
                "precipitation_sum_24h": round(total_precip, 2),
                "precipitation_probability_max": max_precip_prob,
                "condition": dominant_symbol,
            }
        except Exception as e:
            logger.error(f"Error fetching MET Norway forecast: {e}", exc_info=True)
            return None


class BrightSkyClient:
    """
    Async client for Bright Sky (brightsky.dev), the open JSON API in front of the
    official German Weather Service (DWD) data. Used as the local source for German cities.
    """

    BASE_URL = "https://api.brightsky.dev/weather"

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client or httpx.AsyncClient(timeout=15.0)

    async def get_forecast(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Fetch tomorrow's official DWD forecast summary for the given coordinates."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        params = {"lat": f"{lat:.4f}", "lon": f"{lon:.4f}", "date": tomorrow}
        try:
            logger.info(f"Fetching Bright Sky (DWD) forecast for {lat}, {lon}")
            response = await self.client.get(self.BASE_URL, params=params)
            if response.status_code != 200:
                logger.error(f"Bright Sky API returned status code {response.status_code}")
                return None

            records = response.json().get("weather", [])
            if not records:
                return None

            temps = [r["temperature"] for r in records if r.get("temperature") is not None]
            total_precip = sum(r.get("precipitation", 0.0) or 0.0 for r in records)
            conditions = [r.get("condition") for r in records if r.get("condition")]
            dominant = max(set(conditions), key=conditions.count) if conditions else "unknown"

            return {
                "source": "DWD via Bright Sky (brightsky.dev)",
                "temp_max": max(temps) if temps else None,
                "temp_min": min(temps) if temps else None,
                "precipitation_sum_24h": round(total_precip, 2),
                "condition": dominant,
            }
        except Exception as e:
            logger.error(f"Error fetching Bright Sky forecast: {e}", exc_info=True)
            return None


class ApifyWeatherClient:
    """Client for Apify Weather Scrapers (e.g. oneary/weather-database-scraper)"""

    # The two weather actors referenced in the assignment's Data Sources section.
    # We try them in order and return the first that yields data.
    ACTOR_CANDIDATES = [
        ("oneary~weather-database-scraper", {"locations": ["{city}"], "units": "metric", "timeFrame": "ten_day"}),
        ("apify~weather-api", {"location": "{city}", "units": "metric"}),
    ]

    def __init__(self, token: Optional[str] = None, client: Optional[httpx.AsyncClient] = None):
        self.token = token or settings.apify_token
        self.client = client or httpx.AsyncClient(timeout=60.0)

    async def scrape_weather(self, city_name: str) -> Optional[Dict[str, Any]]:
        """Scrape weather details for a city, trying each configured Apify actor in turn."""
        if not self.token:
            logger.warning("Apify API token not configured. Skipping Apify scraper.")
            return None

        for actor_id, payload_template in self.ACTOR_CANDIDATES:
            payload = self._render_payload(payload_template, city_name)
            result = await self._run_actor(actor_id, payload, city_name)
            if result is not None:
                result.setdefault("_apify_actor", actor_id)
                return result

        logger.warning(f"All Apify actors failed to return data for {city_name}.")
        return None

    @staticmethod
    def _render_payload(template: Dict[str, Any], city_name: str) -> Dict[str, Any]:
        """Substitute the {city} placeholder into an actor payload template."""
        rendered: Dict[str, Any] = {}
        for key, value in template.items():
            if isinstance(value, list):
                rendered[key] = [v.replace("{city}", city_name) if isinstance(v, str) else v for v in value]
            elif isinstance(value, str):
                rendered[key] = value.replace("{city}", city_name)
            else:
                rendered[key] = value
        return rendered

    async def _run_actor(self, actor_id: str, payload: Dict[str, Any], city_name: str) -> Optional[Dict[str, Any]]:
        """Run a single Apify actor synchronously and return its first dataset item."""
        url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        params = {"token": self.token}
        try:
            logger.info(f"Running Apify actor '{actor_id}' for {city_name}")
            response = await self.client.post(url, json=payload, params=params)
            if response.status_code in (200, 201):
                dataset_items = response.json()
                if isinstance(dataset_items, list) and dataset_items:
                    logger.info(f"Apify actor '{actor_id}' returned {len(dataset_items)} items for {city_name}")
                    return dataset_items[0]
                if isinstance(dataset_items, dict) and dataset_items:
                    return dataset_items
                logger.info(f"Apify actor '{actor_id}' returned no items for {city_name}")
                return None
            logger.error(f"Apify actor '{actor_id}' returned status {response.status_code}: {response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Error executing Apify actor '{actor_id}': {e}", exc_info=True)
            return None

