import pytest
from app.prediction.model import WeatherPredictionModel

def test_climatology_prior():
    """Verify that prior is calculated correctly from daily precipitation list"""
    model = WeatherPredictionModel()
    hist_data = {
        "daily": {
            "precipitation_sum": [0.0, 1.2, 0.0, 0.0, 5.4, 0.0, 0.0, 0.0, 0.0, 0.0]  # 2 rainy days out of 10
        }
    }
    
    prior = model.calculate_climatology_prior(hist_data)
    assert prior == pytest.approx(0.20)

def test_prediction_ensemble_calibrated():
    """Verify that prediction combining prior and forecast is calibrated correctly"""
    model = WeatherPredictionModel()
    
    # High forecast (80%) and low prior (10%)
    prob, conf, desc = model.predict(
        climatology_prior=0.10,
        forecast_prob=80.0,
        sentiment_score=0.5,  # positive rain news
        market_prob=0.45
    )
    
    assert 0.0 < prob < 1.0
    assert 0.0 < conf < 1.0
    assert len(desc) > 0

def test_edge_and_ev_calculations():
    """Verify edge, fair odds, and EV formulas"""
    model = WeatherPredictionModel()
    
    # Model prob = 70%, Market price = 50 cents (YES)
    edge, ev, fair_odds = model.calculate_edge_and_ev(model_prob=0.70, market_price=0.50, side="YES")
    
    assert edge == pytest.approx(0.20)
    assert ev == pytest.approx(0.20)
    assert fair_odds == pytest.approx(1.42857, rel=1e-3)
    
    # Model prob = 30% (NO probability = 70%), Market price = 60 cents (NO price = 40 cents)
    edge_no, ev_no, fair_no = model.calculate_edge_and_ev(model_prob=0.30, market_price=0.60, side="NO")
    assert edge_no == pytest.approx(0.30)  # (1-0.3) - (1-0.6) = 0.7 - 0.4 = 0.3
    assert ev_no == pytest.approx(0.30)
