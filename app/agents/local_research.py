import logging
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.weather.client import NOAAClient, MetNoClient, BrightSkyClient

logger = logging.getLogger(__name__)

class LocalWeatherResearchAgent(BaseAgent):
    """
    Agent 2: Local Weather Research Agent.
    Collects official country-specific forecasts and alerts from national meteorological
    services: NOAA (US National Weather Service) for the USA, DWD (via Bright Sky) for
    Germany, and MET Norway (Norwegian Meteorological Institute, a global official source)
    for every other country.
    """
    
    SYSTEM_PROMPT = (
        "You are the Local Weather Research Agent. Your job is to analyze local, official government "
        "meteorological alerts, warnings, and statements. Focus on high-impact weather hazards (storms, "
        "extreme heat, localized flooding) that could trigger market movements. Extract critical alerts "
        "and summarize them with precision."
    )

    def __init__(
        self,
        noaa_client: Optional[NOAAClient] = None,
        metno_client: Optional[MetNoClient] = None,
        brightsky_client: Optional[BrightSkyClient] = None,
    ):
        super().__init__(name="LocalWeatherResearchAgent", system_prompt=self.SYSTEM_PROMPT)
        self.noaa = noaa_client or NOAAClient()
        self.metno = metno_client or MetNoClient()
        self.brightsky = brightsky_client or BrightSkyClient()

    async def research_local_agency(
        self,
        city_name: str,
        country: str,
        lat: float,
        lon: float,
        agency_name: str
    ) -> Dict[str, Any]:
        """Query official local agency APIs and parse the resulting forecast and warnings."""
        alerts = []
        forecast_summary = "Local forecast research complete."
        country_key = country.upper()

        # 1. USA -> NOAA (National Weather Service): official forecast + active alerts.
        if country_key in ("USA", "US"):
            logger.info(f"LocalWeatherResearchAgent querying NOAA for {city_name}")
            noaa_forecast = await self.noaa.get_gridpoint_forecast(lat, lon)
            noaa_alerts = await self.noaa.get_alerts_for_coords(lat, lon)

            alerts.extend(noaa_alerts)
            if noaa_forecast and "periods" in noaa_forecast:
                periods = noaa_forecast["periods"]
                if len(periods) > 0:
                    forecast_summary = f"NOAA Official Forecast: {periods[0].get('detailedForecast')}"

        # 2. Germany -> DWD (German Weather Service) via the Bright Sky API.
        elif country_key == "GERMANY":
            logger.info(f"LocalWeatherResearchAgent querying DWD/Bright Sky for {city_name}")
            dwd = await self.brightsky.get_forecast(lat, lon)
            if dwd:
                forecast_summary = (
                    f"{dwd['source']} Official Forecast: condition '{dwd.get('condition')}', "
                    f"high {dwd.get('temp_max')}°C / low {dwd.get('temp_min')}°C, "
                    f"precip {dwd.get('precipitation_sum_24h')}mm."
                )

        # 3. Everywhere else -> MET Norway (official national service, global coverage).
        else:
            logger.info(f"LocalWeatherResearchAgent querying MET Norway for {city_name} ({agency_name})")
            metno = await self.metno.get_forecast(lat, lon)
            if metno:
                forecast_summary = (
                    f"{metno['source']} Official Forecast (regional agency {agency_name}): "
                    f"condition '{metno.get('condition')}', high {metno.get('temp_max')}°C / "
                    f"low {metno.get('temp_min')}°C, 24h precip {metno.get('precipitation_sum_24h')}mm, "
                    f"max precip probability {metno.get('precipitation_probability_max')}%."
                )
            else:
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
