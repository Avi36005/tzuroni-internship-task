import json
import logging
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.risk.kelly import RiskManager

logger = logging.getLogger(__name__)

class RiskAgent(BaseAgent):
    """
    Agent 6: Risk Management Agent.
    Applies Kelly sizing, assesses max exposure, daily drawdowns, and approves or rejects trade sizes.
    """
    
    SYSTEM_PROMPT = (
        "You are the Risk Management Agent. Your job is to enforce strict risk management rules. "
        "You prevent over-exposure, protect portfolio capital, check for drawdown breaches, "
        "and calculate Kelly Criterion position sizes. You output a JSON object containing: "
        "'status' ('APPROVED' or 'REJECTED'), 'allocated_fraction', 'allocated_dollars', and 'reason'."
    )

    def __init__(self, risk_manager: Optional[RiskManager] = None):
        super().__init__(name="RiskAgent", system_prompt=self.SYSTEM_PROMPT)
        self.risk_manager = risk_manager or RiskManager()

    async def evaluate_trade(
        self,
        city_name: str,
        decision: str,
        model_prob: float,
        market_price: float,
        portfolio_value: float,
        current_exposure: float,
        daily_pnl: float
    ) -> Dict[str, Any]:
        """Apply RiskManager rules and generate LLM risk assessment"""
        side = "YES" if "YES" in decision else "NO"
        
        # Calculate sizing using risk manager
        alloc_frac, alloc_dollars, status = self.risk_manager.assess_trade_size(
            model_prob=model_prob,
            market_price=market_price,
            side=side,
            portfolio_value=portfolio_value,
            current_exposure=current_exposure,
            daily_pnl=daily_pnl
        )
        
        # Assess exposure percentage
        exposure_pct = (current_exposure + alloc_dollars) / portfolio_value if portfolio_value > 0 else 0.0
        
        prompt = (
            f"Evaluate risk for trading weather contract in {city_name}:\n"
            f"- Recommended Decision: {decision}\n"
            f"- Model Probability: {model_prob:.1%}\n"
            f"- Market Price: {market_price:.2f}\n"
            f"- Portfolio Value: ${portfolio_value:.2f}\n"
            f"- Current Exposure: ${current_exposure:.2f}\n"
            f"- Daily PnL: ${daily_pnl:+.2f}\n"
            f"- Proposed Sizing: {alloc_frac:.2%} allocation (${alloc_dollars:.2f})\n"
            f"- Sizing Status: {status}\n\n"
            "Format a final risk decision in JSON. Summarize the risk score, Value at Risk impact, "
            "and state if the size is compliant with portfolio limits. Return EXACTLY this format:\n"
            "{\n"
            '  "status": "APPROVED" | "REJECTED",\n'
            '  "allocated_fraction": float,\n'
            '  "allocated_dollars": float,\n'
            '  "reason": "Detailed risk analysis and compliance assessment"\n'
            "}"
        )
        
        response = await self.chat(prompt)
        
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end != -1:
                json_data = json.loads(response[start:end])
                return {
                    "success": True,
                    "status": json_data.get("status", status),
                    "allocated_fraction": float(json_data.get("allocated_fraction", alloc_frac)),
                    "allocated_dollars": float(json_data.get("allocated_dollars", alloc_dollars)),
                    "reason": json_data.get("reason", f"Risk assessment: {status}.")
                }
        except Exception as e:
            logger.warning(f"RiskAgent failed to parse JSON response. Output: {response}. Error: {e}")
            
        return {
            "success": True,
            "status": status,
            "allocated_fraction": alloc_frac,
            "allocated_dollars": alloc_dollars,
            "reason": f"Risk assessment: {status}. Size allocated: {alloc_frac:.2%} of portfolio."
        }
