import pytest
from unittest.mock import AsyncMock, MagicMock
from app.weather.client import OpenMeteoClient, NOAAClient, ApifyWeatherClient

@pytest.mark.asyncio
async def test_open_meteo_forecast():
    """Verify that Open-Meteo client parses API responses correctly"""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "daily": {
            "time": ["2026-07-03"],
            "precipitation_probability_max": [45]
        }
    }
    mock_client.get.return_value = mock_resp
    
    om_client = OpenMeteoClient(client=mock_client)
    res = await om_client.get_forecast(40.71, -74.00)
    
    assert res is not None
    assert res["daily"]["precipitation_probability_max"][0] == 45
    mock_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_noaa_points_and_grid_forecast():
    """Verify that NOAA client maps points to detailed forecasts"""
    mock_client = AsyncMock()
    
    # Mock points response
    point_resp = MagicMock()
    point_resp.status_code = 200
    point_resp.json.return_value = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/OKX/33,37/forecast"
        }
    }
    
    # Mock grid forecast response
    grid_resp = MagicMock()
    grid_resp.status_code = 200
    grid_resp.json.return_value = {
        "periods": [
            {"detailedForecast": "Showers and thunderstorms likely."}
        ]
    }
    
    mock_client.get.side_effect = [point_resp, grid_resp]
    
    noaa_client = NOAAClient(client=mock_client)
    res = await noaa_client.get_gridpoint_forecast(40.71, -74.00)
    
    assert res is not None
    assert res["periods"][0]["detailedForecast"] == "Showers and thunderstorms likely."
    assert mock_client.get.call_count == 2

@pytest.mark.asyncio
async def test_apify_weather_client_success():
    """Verify that Apify client handles weather scraper responses correctly"""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "location": "New York",
            "daily": {
                "time": ["2026-07-03"],
                "precipitation_probability_max": [80]
            }
        }
    ]
    mock_client.post.return_value = mock_resp
    
    apify_client = ApifyWeatherClient(token="mock_apify_token", client=mock_client)
    res = await apify_client.scrape_weather("New York")
    
    assert res is not None
    assert res["location"] == "New York"
    assert res["daily"]["precipitation_probability_max"][0] == 80
    mock_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_apify_weather_client_missing_token():
    """Verify that Apify client skips execution when no token is present"""
    apify_client = ApifyWeatherClient(token="")
    res = await apify_client.scrape_weather("New York")
    assert res is None


from app.notifications.telegram import TelegramNotifier

@pytest.mark.asyncio
async def test_telegram_notifier_success():
    """Verify that Telegram notifier posts messages correctly"""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client.post.return_value = mock_resp
    
    notifier = TelegramNotifier(token="mock_token", chat_id="mock_chat", client=mock_client)
    res = await notifier.send_message("Hello World")
    
    assert res is True
    mock_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_telegram_notifier_missing_credentials():
    """Verify that Telegram notifier skips posting if credentials are not configured"""
    notifier = TelegramNotifier(token="", chat_id="")
    res = await notifier.send_message("Hello World")
    assert res is False


