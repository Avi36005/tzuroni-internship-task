import logging
from typing import Dict, Any, Tuple
from app.config.settings import settings

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Risk Management System using Kelly Criterion and portfolio-level risk constraints.
    Protects capital against drawdown using fractional Kelly sizing and VaR.
    """
    
    def __init__(self, kelly_fraction: float = 0.25, max_exposure: float = 0.10, daily_loss_limit: float = 0.05):
        self.kelly_fraction = kelly_fraction
        self.max_exposure = max_exposure
        self.daily_loss_limit = daily_loss_limit

    def calculate_kelly_size(self, model_prob: float, market_price: float, side: str = "YES") -> float:
        """
        Compute standard Kelly sizing fraction: f* = (p * b - q) / b
        Which simplifies for binary outcome contracts to: f* = (p - price) / (1 - price)
        """
        # Align probability and price with the target side
        p = model_prob if side.upper() == "YES" else 1.0 - model_prob
        price = market_price if side.upper() == "YES" else 1.0 - market_price
        
        if p <= price:
            return 0.0  # No edge, do not trade
            
        # Standard Kelly size
        kelly_raw = (p - price) / (1.0 - price)
        
        # Apply fractional Kelly
        fractional_kelly = kelly_raw * self.kelly_fraction
        
        return float(fractional_kelly)

    def assess_trade_size(
        self,
        model_prob: float,
        market_price: float,
        side: str,
        portfolio_value: float,
        current_exposure: float,
        daily_pnl: float
    ) -> Tuple[float, float, str]:
        """
        Assess risk and calculate final position size in dollars.
        Checks for stop-trading conditions (drawdown limits).
        Returns:
            allocated_fraction: Fraction of portfolio to allocate
            allocated_dollars: Absolute dollar amount to trade
            status: Risk approval message (e.g. APPROVED, REJECTED)
        """
        # 1. Check daily loss limit
        # If daily loss is greater than limit (e.g. -5%), block all trading
        if daily_pnl < 0 and abs(daily_pnl) >= (portfolio_value * self.daily_loss_limit):
            logger.warning(f"Risk Shield: Daily loss limit breached ({daily_pnl:.2f} / {portfolio_value:.2f}). Trading halted.")
            return 0.0, 0.0, "HALTED: DAILY_LOSS_LIMIT"
            
        # 2. Check total portfolio exposure
        # If exposure is already 90% or more, block new trades
        if current_exposure >= (portfolio_value * 0.90):
            logger.warning("Risk Shield: Portfolio exposure exceeds 90%. Sizing restricted to 0.")
            return 0.0, 0.0, "REJECTED: MAX_PORTFOLIO_EXPOSURE"
            
        # 3. Calculate Kelly size
        kelly_frac = self.calculate_kelly_size(model_prob, market_price, side)
        if kelly_frac <= 0:
            return 0.0, 0.0, "NO_TRADE: NO_EDGE"
            
        # 4. Limit by maximum exposure per trade (e.g., 10%)
        final_frac = min(self.max_exposure, kelly_frac)
        
        # 5. Cap size to ensure remaining cash is positive
        max_cash_allowed = portfolio_value - current_exposure
        allocated_dollars = min(portfolio_value * final_frac, max_cash_allowed)
        
        # Recalculate final fraction based on actual dollars allocated
        final_frac = allocated_dollars / portfolio_value if portfolio_value > 0 else 0.0
        
        return final_frac, allocated_dollars, "APPROVED"

    def estimate_var_and_drawdown(
        self,
        portfolio_value: float,
        positions: list
    ) -> Tuple[float, float]:
        """
        Estimate Value at Risk (VaR) and Expected Drawdown.
        VaR is estimated at a 95% confidence level assuming daily volatility.
        """
        if not positions:
            return 0.0, 0.0
            
        # Simple VaR estimation: sum up current exposure and multiply by historical daily weather volatility (~15%)
        # and standard normal multiplier for 95% confidence (1.645)
        total_exposure = sum(pos.shares * pos.current_price for pos in positions)
        daily_volatility = 0.15
        var_95 = total_exposure * daily_volatility * 1.645
        
        # Expected drawdown based on correlation (worst case scenario: all weather events resolve opposite)
        expected_drawdown = total_exposure / portfolio_value if portfolio_value > 0 else 0.0
        
        return round(var_95, 2), round(expected_drawdown, 4)
