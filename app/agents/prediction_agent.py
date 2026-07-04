import json
import logging
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.prediction.model import WeatherPredictionModel

logger = logging.getLogger(__name__)

class PredictionAgent(BaseAgent):
    """
    Agent 5: Prediction Agent.
    Combines forecasts, official local alerts, news sentiment, and market implied probabilities.
    Executes WeatherPredictionModel to calculate EV, edge, and trade decisions (BUY YES / BUY NO / NO TRADE).
    """
    
    SYSTEM_PROMPT = (
        "You are the Prediction Agent. Your job is to act as a Quantitative Decision Engine. "
        "You combine meteorological forecasts, local alerts, sentiment research, and market prices. "
        "You evaluate statistical probabilities, calculate fair odds, compare them against market prices "
        "to calculate EV, and output a JSON decision object containing: "
        "'probability', 'confidence', 'decision' ('BUY YES', 'BUY NO', or 'NO TRADE'), 'reasoning', 'edge', and 'expected_value'."
    )

    def __init__(self, prediction_model: Optional[WeatherPredictionModel] = None):
        super().__init__(name="PredictionAgent", system_prompt=self.SYSTEM_PROMPT)
        self.model = prediction_model or WeatherPredictionModel()

    async def generate_prediction(
        self,
        city_name: str,
        weather_summary: str,
        local_summary: str,
        research_summary: str,
        sentiment_score: float,
        market: Dict[str, Any],
        climatology_prior: float,
        forecast_prob: Optional[float] = None
    ) -> Dict[str, Any]:
        """Combine all inputs, compute quantitative metrics, and return LLM-supported trade decision"""
        market_price = market["yes_price"]
        market_title = market["title"]

        # Use the real meteorological rain probability (%) from the Weather Intel agent.
        # If unavailable, the model falls back to the climatological prior internally.
        parsed_forecast = forecast_prob

        # Run quantitative model
        model_prob, confidence, explanation = self.model.predict(
            climatology_prior=climatology_prior,
            forecast_prob=parsed_forecast,
            sentiment_score=sentiment_score,
            market_prob=market_price
        )
        
        # Calculate EV and Edge for YES
        edge_yes, ev_yes, fair_yes = self.model.calculate_edge_and_ev(model_prob, market_price, "YES")
        
        # Calculate EV and Edge for NO
        edge_no, ev_no, fair_no = self.model.calculate_edge_and_ev(model_prob, market_price, "NO")
        
        # Determine best mathematical decision
        math_decision = "NO TRADE"
        best_edge = 0.0
        best_ev = 0.0
        
        if edge_yes > 0.02 and ev_yes > 0.0:  # Require minimum 2% edge
            math_decision = "BUY YES"
            best_edge = edge_yes
            best_ev = ev_yes
        elif edge_no > 0.02 and ev_no > 0.0:
            math_decision = "BUY NO"
            best_edge = edge_no
            best_ev = ev_no
            
        # 3. Formulate Prompt for LLM to review and write qualitative reasoning
        prompt = (
            f"Review the quantitative prediction metrics for contract: '{market_title}' in {city_name}:\n"
            f"- Market Implied Probability (YES Price): {market_price:.2f} (${market_price*100:.0f}¢)\n"
            f"- Climatology Prior Rain Probability: {climatology_prior:.1%}\n"
            f"- Model Calibrated Probability of Rain: {model_prob:.1%}\n"
            f"- Mathematical Edge: {best_edge:+.1%}\n"
            f"- Expected Value per share: ${best_ev:+.2f}\n"
            f"- Mathematical Recommendation: {math_decision}\n\n"
            f"Context Analysis:\n"
            f"Global Weather Intel: {weather_summary}\n"
            f"Local Government Alerts: {local_summary}\n"
            f"Social & News Research: {research_summary}\n\n"
            "Generate a structured JSON response verifying or overriding the decision based on qualitative warning factors. "
            "Return EXACTLY this JSON format (no other text):\n"
            "{\n"
            '  "probability": float,  // Final model probability\n'
            '  "confidence": float,  // Prediction confidence [0.0 to 1.0]\n'
            '  "decision": "BUY YES" | "BUY NO" | "NO TRADE",\n'
            '  "edge": float,\n'
            '  "expected_value": float,\n'
            '  "reasoning": "Quantitative and qualitative explanation of the trade edge"\n'
            "}"
        )
        
        response = await self.chat(prompt)

        # The Python quantitative model is the authoritative source for the probability,
        # edge, EV and trade decision — these are computed from real per-city forecast,
        # climatology and market data. The LLM contributes qualitative reasoning only, and
        # may (optionally) veto a trade to "NO TRADE" if it flags a strong contradicting
        # signal. This prevents a canned or hallucinated LLM JSON from silently overriding
        # the quant decision with a uniform output.
        reasoning = explanation
        decision = math_decision

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end != -1:
                json_data = json.loads(response[start:end])
                if json_data.get("reasoning"):
                    reasoning = json_data["reasoning"]
                # Allow the LLM to veto (de-risk) but never to manufacture a new trade.
                if json_data.get("decision") == "NO TRADE":
                    decision = "NO TRADE"
        except Exception as e:
            logger.warning(f"PredictionAgent could not parse LLM narrative JSON; using quant reasoning. Error: {e}")

        if decision == "NO TRADE":
            best_edge, best_ev = 0.0, 0.0

        return {
            "success": True,
            "probability_yes": model_prob,
            "probability_no": 1.0 - model_prob,
            "confidence": confidence,
            "decision": decision,
            "edge": best_edge,
            "expected_value": best_ev,
            "reasoning": reasoning
        }
