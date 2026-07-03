import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
from sklearn.metrics import brier_score_loss, precision_score, recall_score, f1_score

logger = logging.getLogger(__name__)

class WeatherPredictionModel:
    """
    Probabilistic quantitative forecasting pipeline.
    Combines climatology (prior), weather forecasts (likelihood), and news sentiment.
    """
    
    def __init__(self):
        pass

    def calculate_climatology_prior(self, historical_data: Dict[str, Any]) -> float:
        """
        Compute historical baseline probability of rain for this date.
        Calculates ratio of historical rainy days (>0.1mm) to total recorded days.
        """
        try:
            if not historical_data or "daily" not in historical_data:
                return 0.20  # default global rain climatology
                
            precipitation = historical_data["daily"].get("precipitation_sum", [])
            if not precipitation:
                return 0.20
                
            # Filter out None values and count rainy days
            valid_precip = [p for p in precipitation if p is not None]
            if not valid_precip:
                return 0.20
                
            rainy_days = sum(1 for p in valid_precip if p > 0.1)
            prior = rainy_days / len(valid_precip)
            
            # Bound prior to avoid absolute certainty
            return min(0.95, max(0.05, prior))
        except Exception as e:
            logger.error(f"Error calculating climatology prior: {e}", exc_info=True)
            return 0.20

    def predict(
        self,
        climatology_prior: float,
        forecast_prob: Optional[float],
        sentiment_score: float,
        market_prob: float
    ) -> Tuple[float, float, str]:
        """
        Combine prior, forecast, and sentiment using a calibrated ensemble model.
        Returns:
            model_probability: Calibrated probability of the event.
            confidence: Estimation confidence based on source agreement.
            explanation: Technical reasoning for the prediction.
        """
        # 1. Base forecast probability (default to prior if None)
        base_forecast = forecast_prob / 100.0 if forecast_prob is not None else climatology_prior
        
        # 2. Sentiment adjustment
        # Positive sentiment (warnings of rain, storms) increases rain probability
        # Negative sentiment (clear skies, sunshine) decreases rain probability
        sentiment_shift = sentiment_score * 0.10  # max 10% shift
        
        # 3. Weighted Ensemble
        # Forecast is given highest weight, climatology acts as stabilizer, sentiment adds marginal edge
        w_forecast = 0.65
        w_climatology = 0.25
        w_sentiment = 0.10
        
        raw_prob = (
            (w_forecast * base_forecast) +
            (w_climatology * climatology_prior) +
            (w_sentiment * max(0.0, min(1.0, base_forecast + sentiment_shift)))
        )
        
        # 4. Calibration (Beta Calibration/Sigmoid scaling to prevent over-confidence)
        # Squeeze values closer to 0.5 when uncertainty is high
        calibrated_prob = 1.0 / (1.0 + np.exp(-3.0 * (raw_prob - 0.5)))
        calibrated_prob = float(np.clip(calibrated_prob, 0.02, 0.98))
        
        # 5. Confidence Calculation
        # Confidence is high if forecast and climatology are aligned, lower if there's high divergence
        divergence = abs(base_forecast - climatology_prior)
        confidence = max(0.3, min(0.95, 1.0 - divergence))
        
        # 6. Technical explanation
        explanation = (
            f"Climatological prior P(Rain)={climatology_prior:.2%}. "
            f"Meteorological forecast indicates P(Forecast)={base_forecast:.2%}. "
            f"Sentiment shift is {sentiment_shift:+.1%}. "
            f"Ensemble raw probability of {raw_prob:.2%} calibrated to {calibrated_prob:.2%} "
            f"with confidence of {confidence:.1%}."
        )
        
        return calibrated_prob, confidence, explanation

    def evaluate_model_performance(self, predictions: list, actual_outcomes: list) -> Dict[str, float]:
        """
        Evaluate statistical metrics of the prediction model.
        Includes Brier Score, Precision, Recall, and F1-Score.
        """
        if not predictions or not actual_outcomes:
            return {
                "brier_score": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0
            }
            
        try:
            preds_np = np.array(predictions)
            outcomes_np = np.array(actual_outcomes, dtype=int)
            
            # Brier Score (lower is better, range [0, 1])
            brier = float(brier_score_loss(outcomes_np, preds_np))
            
            # For classification metrics, convert probabilities to binary outcomes at 0.5 threshold
            preds_binary = (preds_np >= 0.5).astype(int)
            
            precision = float(precision_score(outcomes_np, preds_binary, zero_division=0))
            recall = float(recall_score(outcomes_np, preds_binary, zero_division=0))
            f1 = float(f1_score(outcomes_np, preds_binary, zero_division=0))
            
            return {
                "brier_score": brier,
                "precision": precision,
                "recall": recall,
                "f1_score": f1
            }
        except Exception as e:
            logger.error(f"Error evaluating model performance: {e}", exc_info=True)
            return {
                "brier_score": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0
            }
            
    @staticmethod
    def calculate_edge_and_ev(model_prob: float, market_price: float, side: str = "YES") -> Tuple[float, float, float]:
        """
        Compute market edge, expected value, and fair odds.
        Edge = Model Probability - Market Probability.
        EV = (Probability * Payout) - (1 - Probability) * Price
        """
        # Market price represents market implied probability
        market_prob = market_price
        
        if side.upper() == "YES":
            p = model_prob
            price = market_price
        else:
            p = 1.0 - model_prob
            price = 1.0 - market_price
            
        # Payout is 1.0 per share on resolution
        edge = p - price
        fair_odds = 1.0 / p if p > 0 else 999.0
        
        # Expected value of buying 1 share at 'price'
        ev = (p * 1.0) - price
        
        return edge, ev, fair_odds
