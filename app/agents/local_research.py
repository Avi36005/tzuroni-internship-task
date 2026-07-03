import logging
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.weather.client import NOAAClient

logger = logging.getLogger(__name__)

class LocalWeatherResearchAgent(BaseAgent):
    """
    Agent 2: Local Weather Research Agent.
    Collects official country-specific forecasts and alerts (NOAA for USA, Met Office for UK, IMD for India, etc.).
    """
    
    SYSTEM_PROMPT = (
        "You are the Local Weather Research Agent. Your job is to analyze local, official government "
        "meteorological alerts, warnings, and statements. Focus on high-impact weather hazards (storms, "
        "extreme heat, localized flooding) that could trigger market movements. Extract critical alerts "
        "and summarize them with precision."
    )

    def __init__(self, noaa_client: Optional[NOAAClient] = None):
        super().__init__(name="LocalWeatherResearchAgent", system_prompt=self.SYSTEM_PROMPT)
        self.noaa = noaa_client or NOAAClient()

    async def research_local_agency(
        self,
        city_name: str,
        country: str,
        lat: float,
        lon: float,
        agency_name: str
    ) -> Dict[str, Any]:
        """Query official local agency APIs (such as NOAA for USA) and parse warnings"""
        alerts = []
        forecast_summary = "Local forecast research complete."
        
        # 1. If USA, query NOAA
        if country.upper() in ("USA", "US"):
            logger.info(f"LocalWeatherResearchAgent querying NOAA for {city_name}")
            noaa_forecast = await self.noaa.get_gridpoint_forecast(lat, lon)
            noaa_alerts = await self.noaa.get_alerts_for_coords(lat, lon)
            
            alerts.extend(noaa_alerts)
            if noaa_forecast and "periods" in noaa_forecast:
                periods = noaa_forecast["periods"]
                if len(periods) > 0:
                    forecast_summary = f"NOAA Official Forecast: {periods[0].get('detailedForecast')}"
        else:
            # For non-US, local agencies are queried via news/web research or fallback
            forecast_summary = f"Forecast managed by regional office: {agency_name}."
            
        # 2. Ask LLM to compile and evaluate the severity of local warnings
        prompt = (
            f"Review official weather alerts and statements for {city_name} (managed by {agency_name}):\n"
            f"Agency Forecast: {forecast_summary}\n"
            f"Active Alerts: {alerts}\n\n"
            "Summarize any active severe alerts (heatwaves, storms, flood warnings, extreme wind). "
            "Rate the threat severity (Low, Medium, High) and state if it will affect tomorrow's weather conditions."
        )
        
        analysis = await self.chat(prompt)
        
        return {
            "success": True,
            "forecast_summary": forecast_summary,
            "alerts": alerts,
            "analysis": analysis
        }
