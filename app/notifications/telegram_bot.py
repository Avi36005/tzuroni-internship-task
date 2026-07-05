"""
Interactive Telegram bot (long-polling) for the Weather Prediction AI Trading Agent.

Unlike TelegramNotifier (one-way push notifications), this module listens for user
commands via getUpdates and replies with live data read from the trading database:

    /start | /help   -> command list
    /status          -> portfolio value, cash, exposure, open positions, Sharpe
    /portfolio       -> full open-position breakdown with PnL
    /predictions     -> latest model predictions per market
    /trades          -> recent executed orders
    /run             -> trigger one full workflow cycle on demand

Run it with:  PYTHONPATH=. python scripts/run_bot.py
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select

from app.config.settings import settings
from app.database.db import async_session
from app.database.models import Market, Order, PortfolioState, Position, Prediction

logger = logging.getLogger(__name__)


class TelegramBot:
    """Long-polling Telegram bot that answers commands from the trading database."""

    API = "https://api.telegram.org/bot{token}/{method}"

    def __init__(
        self,
        token: Optional[str] = None,
        allowed_chat_id: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.token = token if token is not None else settings.telegram_token
        # If set, only this chat may command the bot (defaults to the configured chat).
        self.allowed_chat_id = (
            allowed_chat_id if allowed_chat_id is not None else settings.telegram_chat_id
        )
        self.client = client or httpx.AsyncClient(timeout=40.0)
        self._offset: Optional[int] = None
        self._running = False

    # ---- Telegram transport -------------------------------------------------

    async def _call(self, method: str, **params) -> Optional[Dict[str, Any]]:
        url = self.API.format(token=self.token, method=method)
        try:
            resp = await self.client.post(url, json=params)
            data = resp.json()
            if not data.get("ok"):
                logger.error(f"Telegram {method} error: {data}")
                return None
            return data.get("result")
        except Exception as e:
            logger.error(f"Telegram {method} request failed: {e}", exc_info=True)
            return None

    async def send(self, chat_id: str, text: str) -> None:
        await self._call("sendMessage", chat_id=chat_id, text=text, parse_mode="Markdown")

    # ---- Command handlers ---------------------------------------------------

    async def handle_command(self, chat_id: str, text: str) -> None:
        command = text.strip().split()[0].lstrip("/").lower()
        # Strip @BotName suffix (Telegram appends it in groups).
        command = command.split("@")[0]

        handlers = {
            "start": self._cmd_help,
            "help": self._cmd_help,
            "status": self._cmd_status,
            "portfolio": self._cmd_portfolio,
            "predictions": self._cmd_predictions,
            "trades": self._cmd_trades,
            "run": self._cmd_run,
        }
        handler = handlers.get(command)
        if handler is None:
            await self.send(chat_id, "❓ Unknown command. Send /help for the list.")
            return
        await handler(chat_id)

    async def _cmd_help(self, chat_id: str) -> None:
        await self.send(
            chat_id,
            "🤖 *Weather AI Trading Agent*\n\n"
            "Available commands:\n"
            "• /status — portfolio snapshot & risk\n"
            "• /portfolio — open positions & PnL\n"
            "• /predictions — latest model predictions\n"
            "• /trades — recent executed orders\n"
            "• /run — run one trading workflow cycle\n"
            "• /help — show this message",
        )

    async def _cmd_status(self, chat_id: str) -> None:
        async with async_session() as session:
            state = (
                await session.execute(
                    select(PortfolioState).order_by(PortfolioState.timestamp.desc()).limit(1)
                )
            ).scalar_one_or_none()
            positions = (await session.execute(select(Position))).scalars().all()

            if state is None:
                await self.send(chat_id, "📭 No portfolio state yet. Run /run to start a cycle.")
                return

            from app.portfolio.manager import PortfolioManager

            stats = await PortfolioManager().calculate_portfolio_statistics(session)

        pnl = state.portfolio_value - settings.starting_balance
        await self.send(
            chat_id,
            "📊 *Portfolio Status*\n\n"
            f"💰 Value: ${state.portfolio_value:,.2f}\n"
            f"💵 Cash: ${state.cash:,.2f}\n"
            f"📈 Total PnL: ${pnl:+,.2f} ({pnl / settings.starting_balance:+.2%})\n"
            f"🔓 Exposure: ${state.exposure:,.2f}\n"
            f"📉 Unrealized PnL: ${state.unrealized_pnl:+,.2f}\n"
            f"💼 Open positions: {len(positions)}\n"
            f"⚖️ Sharpe: {stats['sharpe_ratio']} · Max DD: {stats['max_drawdown']:.2%}",
        )

    async def _cmd_portfolio(self, chat_id: str) -> None:
        async with async_session() as session:
            positions = (await session.execute(select(Position))).scalars().all()
            if not positions:
                await self.send(chat_id, "💼 No open positions.")
                return
            lines = ["💼 *Open Positions*\n"]
            for p in positions[:25]:
                market = (
                    await session.execute(select(Market).where(Market.id == p.market_id))
                ).scalar_one_or_none()
                title = (market.title[:28] if market else f"Market {p.market_id}")
                lines.append(
                    f"• {title} | {p.side} | {p.shares:.0f} sh @ ${p.average_price:.2f} "
                    f"→ ${p.current_price:.2f} | PnL ${p.pnl:+.2f}"
                )
        await self.send(chat_id, "\n".join(lines))

    async def _cmd_predictions(self, chat_id: str) -> None:
        async with async_session() as session:
            preds = (
                await session.execute(
                    select(Prediction).order_by(Prediction.created_at.desc()).limit(10)
                )
            ).scalars().all()
            if not preds:
                await self.send(chat_id, "🔮 No predictions recorded yet.")
                return
            lines = ["🔮 *Latest Predictions*\n"]
            for p in preds:
                market = (
                    await session.execute(select(Market).where(Market.id == p.market_id))
                ).scalar_one_or_none()
                title = (market.title[:26] if market else f"Market {p.market_id}")
                lines.append(
                    f"• {title} | P(YES) {p.model_probability_yes:.0%} | "
                    f"edge {p.edge:+.0%} | {p.decision}"
                )
        await self.send(chat_id, "\n".join(lines))

    async def _cmd_trades(self, chat_id: str) -> None:
        async with async_session() as session:
            orders = (
                await session.execute(
                    select(Order).order_by(Order.executed_at.desc()).limit(10)
                )
            ).scalars().all()
            if not orders:
                await self.send(chat_id, "📜 No trades executed yet.")
                return
            lines = ["📜 *Recent Trades*\n"]
            for o in orders:
                market = (
                    await session.execute(select(Market).where(Market.id == o.market_id))
                ).scalar_one_or_none()
                title = (market.title[:26] if market else f"Market {o.market_id}")
                lines.append(
                    f"• {title} | {o.side} | {o.amount:.0f} sh @ ${o.price:.2f} "
                    f"| cost ${o.cost:.2f}"
                )
        await self.send(chat_id, "\n".join(lines))

    async def _cmd_run(self, chat_id: str) -> None:
        await self.send(chat_id, "⏳ Running a full trading workflow cycle… this may take a moment.")
        try:
            # Imported lazily to avoid a heavy import at bot startup.
            from app.agents.supervisor import SupervisorAgent

            supervisor = SupervisorAgent()
            async with async_session() as session:
                await supervisor.seed_cities(session)
                result = await supervisor.run_workflow(session)
            await self.send(
                chat_id,
                "✅ *Cycle complete*\n\n"
                f"📈 Trades: {result['trades_executed']} · 🛡️ Hedges: {result['hedges_executed']}\n"
                f"💰 Value: ${result['portfolio_value']:,.2f} · 💵 Cash: ${result['cash']:,.2f}",
            )
        except Exception as e:
            logger.error(f"/run cycle failed: {e}", exc_info=True)
            await self.send(chat_id, f"❌ Cycle failed: {e}")

    # ---- Polling loop -------------------------------------------------------

    def _authorized(self, chat_id: str) -> bool:
        if not self.allowed_chat_id:
            return True  # no restriction configured
        return str(chat_id) == str(self.allowed_chat_id)

    async def _process_update(self, update: Dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return
        text = message.get("text", "")
        chat_id = str(message.get("chat", {}).get("id", ""))
        if not text.startswith("/"):
            return
        if not self._authorized(chat_id):
            logger.warning(f"Ignoring command from unauthorized chat {chat_id}")
            return
        logger.info(f"Bot received command '{text}' from chat {chat_id}")
        await self.handle_command(chat_id, text)

    async def run_forever(self) -> None:
        """Poll Telegram for updates and dispatch commands until stopped."""
        if not self.token:
            raise RuntimeError("TELEGRAM_TOKEN not configured; cannot start the bot.")

        me = await self._call("getMe")
        if me:
            logger.info(f"Telegram bot @{me.get('username')} started (long-polling).")

        self._running = True
        while self._running:
            updates = await self._call(
                "getUpdates", offset=self._offset, timeout=30
            )
            if not updates:
                continue
            for update in updates:
                self._offset = update["update_id"] + 1
                try:
                    await self._process_update(update)
                except Exception as e:
                    logger.error(f"Error processing update: {e}", exc_info=True)

    def stop(self) -> None:
        self._running = False
