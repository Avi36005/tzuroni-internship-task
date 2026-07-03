import pytest
from app.risk.kelly import RiskManager

def test_kelly_sizing_calculation():
    """Verify Kelly formula: f* = (p - price) / (1 - price)"""
    manager = RiskManager(kelly_fraction=0.25)
    
    # 25% Kelly, p=60%, price=40 cents. YES.
    # Raw Kelly = (0.6 - 0.4) / (1.0 - 0.4) = 0.2 / 0.6 = 0.3333
    # 25% Kelly = 0.3333 * 0.25 = 0.0833
    size = manager.calculate_kelly_size(model_prob=0.60, market_price=0.40, side="YES")
    assert size == pytest.approx(0.0833, rel=1e-2)
    
    # No edge (p <= price) should return 0 sizing
    no_size = manager.calculate_kelly_size(model_prob=0.30, market_price=0.50, side="YES")
    assert no_size == 0.0

def test_assess_trade_size_limits():
    """Verify that portfolio risk limits restrict size correctly"""
    # Max exposure 10%, daily loss limit 5%
    manager = RiskManager(kelly_fraction=1.0, max_exposure=0.10, daily_loss_limit=0.05)
    
    # Large Kelly size (e.g. p=90%, price=40 cents -> Raw Kelly = 0.5/0.6 = 83%)
    # Sizing should be capped by max_exposure (10%)
    alloc_frac, alloc_dollars, status = manager.assess_trade_size(
        model_prob=0.90,
        market_price=0.40,
        side="YES",
        portfolio_value=10000.0,
        current_exposure=0.0,
        daily_pnl=0.0
    )
    
    assert status == "APPROVED"
    assert alloc_frac == pytest.approx(0.10)
    assert alloc_dollars == pytest.approx(1000.0)

def test_daily_loss_limit_halt():
    """Verify that trading halts if daily loss limit is breached"""
    manager = RiskManager(daily_loss_limit=0.05)
    
    # Daily PnL is -$600, which is -6% of $10,000 portfolio (limit is 5%)
    alloc_frac, alloc_dollars, status = manager.assess_trade_size(
        model_prob=0.80,
        market_price=0.40,
        side="YES",
        portfolio_value=10000.0,
        current_exposure=0.0,
        daily_pnl=-600.0
    )
    
    assert status == "HALTED: DAILY_LOSS_LIMIT"
    assert alloc_frac == 0.0
    assert alloc_dollars == 0.0
