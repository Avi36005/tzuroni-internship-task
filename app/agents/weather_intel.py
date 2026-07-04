import logging
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.weather.client import OpenMeteoClient, ApifyWeatherClient

logger = logging.getLogger(__name__)

class WeatherIntelAgent(BaseAgent):
    """
    Agent 1: Weather Intelligence Agent.
    Fetches global weather forecast, temperature, wind, rain probability, anomalies, and severe weather alerts.
    Utilizes Apify scraper with Open-Meteo fallback.
    """
    
    SYSTEM_PROMPT = (
        "You are the Weather Intelligence Agent. Your job is to analyze global weather forecast data, "
        "identify anomalies, estimate forecast uncertainty, and summarize meteorological outlooks "
        "for prediction market trading. Keep your summaries highly quantitative, structured, and factual."
    )

    def __init__(self, open_meteo_client: Optional[OpenMeteoClient] = None, apify_client: Optional[ApifyWeatherClient] = None):
        super().__init__(name="WeatherIntelAgent", system_prompt=self.SYSTEM_PROMPT)
        self.open_meteo = open_meteo_client or OpenMeteoClient()
        self.apify = apify_client or ApifyWeatherClient()

    async def analyze_city(self, city_name: str, lat: float, lon: float) -> Dict[str, Any]:
        """Fetch weather details using Apify scraper, falling back to Open-Meteo forecast"""
        apify_data = await self.apify.scrape_weather(city_name)
        
        forecast = None
        if apify_data:
            logger.info(f"WeatherIntelAgent: Successfully retrieved Apify data for {city_name}")
            # Map Apify data format if possible, otherwise keep it as raw
            forecast = apify_data
            
        # Fallback to Open-Meteo forecast if Apify returned nothing
        if not forecast or "daily" not in forecast:
            logger.info(f"WeatherIntelAgent: Apify data unavailable for {city_name}. Falling back to Open-Meteo.")
            forecast = await self.open_meteo.get_forecast(lat, lon)
        
        if not forecast or "daily" not in forecast:
            logger.error(f"WeatherIntelAgent failed to fetch forecast for {city_name}")
            return {
                "success": False,
                "summary": "Weather forecast unavailable.",
                "forecast_raw": {},
                "forecast_precip_probability": None
            }

        daily = forecast["daily"]
        # Format a prompt with the daily forecast data
        prompt = (
            f"Analyze the following daily weather forecast data for {city_name} (Coordinates: {lat}, {lon}):\n"
            f"Dates: {daily.get('time')}\n"
            f"Max Temperatures (°C): {daily.get('temperature_2m_max')}\n"
            f"Min Temperatures (°C): {daily.get('temperature_2m_min')}\n"
            f"Precipitation Sums (mm): {daily.get('precipitation_sum')}\n"
            f"Max Rain Probability (%): {daily.get('precipitation_probability_max')}\n"
            f"Max Wind Speeds (km/h): {daily.get('wind_speed_10m_max')}\n"
            f"Mean Pressure (hPa): {daily.get('surface_pressure_mean')}\n\n"
            "Provide a concise summary. Highlight any weather anomalies (e.g. extreme temperatures or sudden pressure drops), "
            "assess source confidence (meteorological variance), and state the precipitation risk for tomorrow."
        )
        
        analysis = await self.chat(prompt)

        # Extract tomorrow's rain probability so downstream agents use the real forecast
        # rather than a hardcoded value. Index 0 is today, index 1 is tomorrow.
        precip_probs = daily.get("precipitation_probability_max") or []
        forecast_prob: Optional[float] = None
        if len(precip_probs) > 1 and precip_probs[1] is not None:
            forecast_prob = float(precip_probs[1])
        elif len(precip_probs) > 0 and precip_probs[0] is not None:
            forecast_prob = float(precip_probs[0])

        return {
            "success": True,
            "summary": analysis,
            "forecast_raw": forecast,
            "forecast_precip_probability": forecast_prob
        }

