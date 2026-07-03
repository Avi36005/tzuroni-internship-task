import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.base import BaseAgent
from app.portfolio.manager import PortfolioManager

logger = logging.getLogger(__name__)

class PortfolioAgent(BaseAgent):
    """
    Agent 8: Portfolio Agent.
    Maintains capital account, open positions, revalues holdings, and calculates performance metrics
    (Sharpe Ratio, Sortino Ratio, Drawdown, Profit Factor).
    """
    
    SYSTEM_PROMPT = (
        "You are the Portfolio Agent. Your job is to monitor and report on portfolio performance. "
        "You summarize open positions, calculate returns, analyze risk-adjusted metrics like the Sharpe "
        "and Sortino ratios, and write daily portfolio health reports. Keep your style highly professional."
    )

    def __init__(self, portfolio_manager: Optional[PortfolioManager] = None):
        super().__init__(name="PortfolioAgent", system_prompt=self.SYSTEM_PROMPT)
        self.manager = portfolio_manager or PortfolioManager()

    async def generate_portfolio_report(self, session: AsyncSession) -> Dict[str, Any]:
        """Update portfolio valuation and generate performance statistics summary"""
        # Revalue portfolio first
        portfolio_state = await self.manager.update_portfolio_valuation(session)
        
        # Calculate stats
        stats = await self.manager.calculate_portfolio_statistics(session)
        
        # Generate LLM summary report
        prompt = (
            f"Review the current portfolio state and statistics:\n"
            f"- Total Portfolio Value: ${portfolio_state.portfolio_value:.2f}\n"
            f"- Cash Balance: ${portfolio_state.cash:.2f}\n"
            f"- Current Exposure: ${portfolio_state.exposure:.2f}\n"
            f"- Unrealized PnL: ${portfolio_state.unrealized_pnl:+.2f}\n"
            f"- Annualized Sharpe Ratio: {stats['sharpe_ratio']:.4f}\n"
            f"- Annualized Sortino Ratio: {stats['sortino_ratio']:.4f}\n"
            f"- Maximum Drawdown: {stats['max_drawdown']:.2%}\n"
            f"- Daily Return: {portfolio_state.daily_return:+.4%}\n\n"
            "Write a concise, Bloomberg-style portfolio performance report. Highlight capital efficiency, "
            "exposure risk, and drawdown safety."
        )
        
        report = await self.chat(prompt)
        
        return {
            "success": True,
            "portfolio_value": portfolio_state.portfolio_value,
            "cash": portfolio_state.cash,
            "exposure": portfolio_state.exposure,
            "stats": stats,
            "report": report
        }
