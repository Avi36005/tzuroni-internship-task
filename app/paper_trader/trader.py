import logging
import random
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from app.database.models import Order, Position, Market, PortfolioState, City
from app.config.settings import settings

logger = logging.getLogger(__name__)

class PaperTrader:
    """
    Simulated order execution engine matching the schema of polymarket-paper-trader.
    Calculates execution price, slippage, fees, and updates positions and portfolio balances.
    """
    
    def __init__(self):
        pass

    async def place_order(
        self,
        session: AsyncSession,
        market: Market,
        side: str,
        cost_dollars: float,
        reason: str
    ) -> Optional[Order]:
        """
        Execute a simulated market order.
        Calculates slippage based on market liquidity and order size, updates Cash and Positions.
        """
        try:
            side = side.upper()
            if side not in ("YES", "NO"):
                raise ValueError("Side must be YES or NO")
                
            # 1. Fetch current portfolio state
            stmt = select(PortfolioState).order_by(PortfolioState.timestamp.desc()).limit(1)
            result = await session.execute(stmt)
            portfolio = result.scalar_one_or_none()
            
            if not portfolio:
                # Initialize portfolio state if not present
                portfolio = PortfolioState(
                    cash=settings.starting_balance,
                    portfolio_value=settings.starting_balance,
                    unrealized_pnl=0.0,
                    daily_return=0.0,
                    exposure=0.0,
                    max_drawdown=0.0
                )
                session.add(portfolio)
                await session.flush()
                
            if portfolio.cash < cost_dollars:
                logger.error(f"Insufficient funds for order. Cash: {portfolio.cash:.2f}, Cost: {cost_dollars:.2f}")
                return None
                
            # 2. Calculate execution price and slippage
            base_price = market.yes_price if side == "YES" else market.no_price
            
            # Market impact model: slippage increases with trade size relative to liquidity
            liquidity = max(100.0, market.liquidity)
            slippage_pct = min(0.10, (cost_dollars / liquidity) * 0.05)  # cap slippage at 10%
            slippage_cost = base_price * slippage_pct
            execution_price = base_price + slippage_cost
            
            # Ensure price does not exceed 0.99
            execution_price = min(0.99, max(0.01, execution_price))
            
            # 3. Calculate shares bought
            shares = cost_dollars / execution_price
            
            # 4. Create Order record
            order = Order(
                market_id=market.id,
                side=side,
                price=execution_price,
                amount=shares,
                cost=cost_dollars,
                reason=reason,
                status="FILLED",
                slippage=slippage_pct,
                executed_at=datetime.utcnow()
            )
            session.add(order)
            
            # 5. Update or Create Position
            pos_stmt = select(Position).where(Position.market_id == market.id, Position.side == side)
            pos_result = await session.execute(pos_stmt)
            position = pos_result.scalar_one_or_none()
            
            if position:
                # Average down / up cost basis
                new_shares = position.shares + shares
                new_avg = ((position.average_price * position.shares) + (execution_price * shares)) / new_shares
                position.shares = new_shares
                position.average_price = new_avg
                position.current_price = base_price
                position.updated_at = datetime.utcnow()
            else:
                position = Position(
                    market_id=market.id,
                    side=side,
                    average_price=execution_price,
                    shares=shares,
                    current_price=base_price,
                    pnl=0.0,
                    is_hedged=False,
                    updated_at=datetime.utcnow()
                )
                session.add(position)
                
            # 6. Deduct cash from portfolio
            portfolio.cash -= cost_dollars
            portfolio.exposure += cost_dollars
            portfolio.timestamp = datetime.utcnow()
            
            await session.commit()
            logger.info(f"Order filled: Bought {shares:.2f} shares of {market.slug} ({side}) at {execution_price:.2f}. Total cost: ${cost_dollars:.2f}")
            return order
            
        except Exception as e:
            logger.error(f"Error executing paper trade: {e}", exc_info=True)
            await session.rollback()
            return None

    async def resolve_expired_markets(
        self,
        session: AsyncSession,
        market_resolutions: Dict[str, str]  # slug -> resolved_side ("YES" or "NO")
    ) -> List[Dict[str, Any]]:
        """
        Process settlement of expired contracts.
        Adds cash payouts ($1.00 per winning share) and removes resolved positions.
        """
        settlements = []
        try:
            # 1. Fetch current portfolio
            stmt = select(PortfolioState).order_by(PortfolioState.timestamp.desc()).limit(1)
            result = await session.execute(stmt)
            portfolio = result.scalar_one_or_none()
            
            if not portfolio:
                return []
                
            # 2. Process positions for resolved markets
            for slug, resolved_side in market_resolutions.items():
                m_stmt = select(Market).where(Market.slug == slug)
                m_result = await session.execute(m_stmt)
                market = m_result.scalar_one_or_none()
                
                if not market:
                    continue
                    
                pos_stmt = select(Position).where(Position.market_id == market.id)
                pos_result = await session.execute(pos_stmt)
                positions = pos_result.scalars().all()
                
                for pos in positions:
                    shares = pos.shares
                    avg_price = pos.average_price
                    total_cost = shares * avg_price
                    
                    if pos.side == resolved_side:
                        # Winning position pays out $1.00 per share
                        payout = shares * 1.0
                        realized_pnl = payout - total_cost
                        portfolio.cash += payout
                        outcome = "WIN"
                    else:
                        # Losing position pays out $0.00
                        payout = 0.0
                        realized_pnl = -total_cost
                        outcome = "LOSS"
                        
                    # Update exposure
                    portfolio.exposure = max(0.0, portfolio.exposure - total_cost)
                    
                    settlements.append({
                        "market_slug": slug,
                        "title": market.title,
                        "side": pos.side,
                        "shares": shares,
                        "average_price": avg_price,
                        "payout": payout,
                        "realized_pnl": realized_pnl,
                        "outcome": outcome
                    })
                    
                    # Delete position
                    await session.delete(pos)
                    
                # Mark market as inactive
                market.is_active = False
                market.yes_price = 1.0 if resolved_side == "YES" else 0.0
                market.no_price = 0.0 if resolved_side == "YES" else 1.0
                
            portfolio.timestamp = datetime.utcnow()
            await session.commit()
            
            if settlements:
                logger.info(f"Resolved {len(settlements)} contracts. Settlements processed.")
            return settlements
            
        except Exception as e:
            logger.error(f"Error resolving expired markets: {e}", exc_info=True)
            await session.rollback()
            return []
