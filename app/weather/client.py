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


class ApifyWeatherClient:
    """Client for Apify Weather Scrapers (e.g. oneary/weather-database-scraper)"""
    
    def __init__(self, token: Optional[str] = None, client: Optional[httpx.AsyncClient] = None):
        self.token = token or settings.apify_token
        self.client = client or httpx.AsyncClient(timeout=30.0)

    async def scrape_weather(self, city_name: str) -> Optional[Dict[str, Any]]:
        """Scrape weather details for a specific city from Apify"""
        if not self.token:
            logger.warning("Apify API token not configured. Skipping Apify scraper.")
            return None
        
        # Use the oneary/weather-database-scraper actor API url
        actor_id = "oneary~weather-database-scraper"
        url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        
        payload = {
            "locations": [city_name],
            "units": "metric",
            "timeFrame": "ten_day"
        }
        
        params = {
            "token": self.token
        }
        
        try:
            logger.info(f"Running Apify weather scraper for {city_name}")
            response = await self.client.post(url, json=payload, params=params)
            
            if response.status_code in [200, 201]:
                dataset_items = response.json()
                logger.info(f"Apify scraper returned {len(dataset_items)} items for {city_name}")
                if dataset_items:
                    return dataset_items[0] if isinstance(dataset_items, list) else dataset_items
                return None
            else:
                logger.error(f"Apify API returned status code {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error executing Apify weather scraper: {e}", exc_info=True)
            return None

