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
    """Verify the Apify client normalises scraped daily records into Open-Meteo format"""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    # cloud9_ai/open-meteo-scraper returns a flat list of daily records.
    mock_resp.json.return_value = [
        {
            "locationName": "New York", "date": "2026-07-03",
            "temperatureMax": 30, "temperatureMin": 20,
            "precipitation": 2.5, "windSpeedMax": 15,
            "weatherCode": 63, "weatherDescription": "Rain",
        },
        {
            "locationName": "New York", "date": "2026-07-04",
            "temperatureMax": 28, "temperatureMin": 19,
            "precipitation": 0, "windSpeedMax": 12,
            "weatherCode": 1, "weatherDescription": "Mainly clear",
        },
    ]
    mock_client.post.return_value = mock_resp

    apify_client = ApifyWeatherClient(token="mock_apify_token", client=mock_client)
    res = await apify_client.scrape_weather("New York", lat=40.71, lon=-74.00)

    assert res is not None
    assert res["_source"] == "apify:cloud9_ai/open-meteo-scraper"
    daily = res["daily"]
    assert daily["time"] == ["2026-07-03", "2026-07-04"]
    assert daily["temperature_2m_max"] == [30, 28]
    # Day 1: WMO 63 (rain) + 2.5mm precip -> high probability; Day 2: WMO 1 -> low.
    assert daily["precipitation_probability_max"][0] > daily["precipitation_probability_max"][1]
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_apify_weather_client_missing_token():
    """Verify that Apify client skips execution when no token is present"""
    apify_client = ApifyWeatherClient(token="")
    res = await apify_client.scrape_weather("New York", lat=40.71, lon=-74.00)
    assert res is None


@pytest.mark.asyncio
async def test_apify_weather_client_missing_coords():
    """Verify that Apify client skips execution when coordinates are missing"""
    apify_client = ApifyWeatherClient(token="mock_apify_token")
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
