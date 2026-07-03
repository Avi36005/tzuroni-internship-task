import logging
import json
from datetime import datetime, timedelta
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional

from app.database.models import City, WeatherData, ResearchResult, Market, Prediction, Order, Position, PortfolioState
from app.agents.weather_intel import WeatherIntelAgent
from app.agents.local_research import LocalWeatherResearchAgent
from app.agents.market_agent import MarketAgent
from app.agents.research_agent import ResearchAgent
from app.agents.prediction_agent import PredictionAgent
from app.agents.risk_agent import RiskAgent
from app.agents.execution_agent import ExecutionAgent
from app.agents.portfolio_agent import PortfolioAgent
from app.agents.hedging_agent import HedgingAgent
from app.markets.polymarket import PolymarketClient
from app.weather.client import OpenMeteoClient
from app.notifications.telegram import TelegramNotifier

logger = logging.getLogger(__name__)

# List of 20 default cities to seed the system
DEFAULT_CITIES = [
    {"name": "New York", "country": "USA", "latitude": 40.7128, "longitude": -74.0060, "local_agency": "NOAA"},
    {"name": "London", "country": "UK", "latitude": 51.5074, "longitude": -0.1278, "local_agency": "Met Office"},
    {"name": "Mumbai", "country": "India", "latitude": 19.0760, "longitude": 72.8777, "local_agency": "IMD"},
    {"name": "Tokyo", "country": "Japan", "latitude": 35.6762, "longitude": 139.6503, "local_agency": "JMA"},
    {"name": "Sydney", "country": "Australia", "latitude": -33.8688, "longitude": 151.2093, "local_agency": "BOM"},
    {"name": "Berlin", "country": "Germany", "latitude": 52.5200, "longitude": 13.4050, "local_agency": "DWD"},
    {"name": "Paris", "country": "France", "latitude": 48.8566, "longitude": 2.3522, "local_agency": "MeteoFrance"},
    {"name": "Singapore", "country": "Singapore", "latitude": 1.3521, "longitude": 103.8198, "local_agency": "MSS"},
    {"name": "Toronto", "country": "Canada", "latitude": 43.6532, "longitude": -79.3832, "local_agency": "MSC"},
    {"name": "Dubai", "country": "UAE", "latitude": 25.2048, "longitude": 55.2708, "local_agency": "NCM"},
    {"name": "Delhi", "country": "India", "latitude": 28.6139, "longitude": 77.2090, "local_agency": "IMD"},
    {"name": "Hong Kong", "country": "Hong Kong", "latitude": 22.3193, "longitude": 114.1694, "local_agency": "HKO"},
    {"name": "Los Angeles", "country": "USA", "latitude": 34.0522, "longitude": -118.2437, "local_agency": "NOAA"},
    {"name": "Chicago", "country": "USA", "latitude": 41.8781, "longitude": -87.6298, "local_agency": "NOAA"},
    {"name": "Rome", "country": "Italy", "latitude": 41.9028, "longitude": 12.4964, "local_agency": "Aeronautica"},
    {"name": "Amsterdam", "country": "Netherlands", "latitude": 52.3676, "longitude": 4.9041, "local_agency": "KNMI"},
    {"name": "Madrid", "country": "Spain", "latitude": 40.4168, "longitude": -3.7038, "local_agency": "AEMET"},
    {"name": "Melbourne", "country": "Australia", "latitude": -37.8136, "longitude": 144.9631, "local_agency": "BOM"},
    {"name": "Seoul", "country": "South Korea", "latitude": 37.5665, "longitude": 126.9780, "local_agency": "KMA"},
    {"name": "Bangkok", "country": "Thailand", "latitude": 13.7563, "longitude": 100.5018, "local_agency": "TMD"}
]

class SupervisorAgent:
    """
    Agent 10: Supervisor Agent.
    Orchestrates the entire weather prediction and trading workflow.
    Handles scheduling, database updates, contract settlements, and system monitoring.
    """
    
    def __init__(self):
        self.weather_intel = WeatherIntelAgent()
        self.local_research = LocalWeatherResearchAgent()
        self.market_agent = MarketAgent()
        self.research_agent = ResearchAgent()
        self.prediction_agent = PredictionAgent()
        self.risk_agent = RiskAgent()
        self.execution_agent = ExecutionAgent()
        self.portfolio_agent = PortfolioAgent()
        self.hedging_agent = HedgingAgent()
        
        self.polymarket_client = PolymarketClient()
        self.open_meteo = OpenMeteoClient()
        self.telegram = TelegramNotifier()


    async def seed_cities(self, session: AsyncSession):
        """Seed 20 supported cities into the database if empty"""
        result = await session.execute(select(City))
        cities = result.scalars().all()
        if not cities:
            logger.info("Seeding 20 supported cities in the database.")
            for c in DEFAULT_CITIES:
                session.add(City(**c))
            await session.commit()

    async def run_workflow(self, session: AsyncSession) -> Dict[str, Any]:
        """Execute one complete cycle of the multi-agent trading system"""
        logger.info("Supervisor Agent: Starting workflow cycle...")
        
        # 1. Seed and load cities
        await self.seed_cities(session)
        city_stmt = select(City)
        city_result = await session.execute(city_stmt)
        cities = city_result.scalars().all()
        cities_list = [{"id": c.id, "name": c.name, "latitude": c.latitude, "longitude": c.longitude, "local_agency": c.local_agency} for c in cities]
        
        # 2. Settle expired markets first
        await self._settle_expired_contracts(session, cities)
        
        # 3. Load active portfolio metrics
        port_state = await self.portfolio_agent.generate_portfolio_report(session)
        portfolio_value = port_state["portfolio_value"]
        cash = port_state["cash"]
        exposure = port_state["exposure"]
        daily_pnl = port_state["stats"]["current_portfolio_value"] - 10000.0  # simple daily pnl estimation
        
        # 4. Fetch weather markets from Polymarket Client
        available_markets = await self.polymarket_client.get_active_markets(cities_list)
        
        # Write markets to DB
        db_markets = []
        for m in available_markets:
            city_id = m.get("city_id")
            if not city_id:
                # Resolve city_id by name if not populated
                for c in cities:
                    if c.name.lower() in m["title"].lower():
                        city_id = c.id
                        break
                if not city_id:
                    continue  # skip markets not in our 20 cities
                    
            m_stmt = select(Market).where(Market.slug == m["slug"])
            m_result = await session.execute(m_stmt)
            db_m = m_result.scalar_one_or_none()
            
            if db_m:
                db_m.yes_price = m["yes_price"]
                db_m.no_price = m["no_price"]
                db_m.implied_probability = m["implied_probability"]
                db_m.volume = m["volume"]
                db_m.liquidity = m["liquidity"]
                db_m.spread = m["spread"]
            else:
                db_m = Market(
                    city_id=city_id,
                    title=m["title"],
                    slug=m["slug"],
                    condition_id=m["condition_id"],
                    clob_token_id_yes=m["clob_token_id_yes"],
                    clob_token_id_no=m["clob_token_id_no"],
                    yes_price=m["yes_price"],
                    no_price=m["no_price"],
                    implied_probability=m["implied_probability"],
                    volume=m["volume"],
                    liquidity=m["liquidity"],
                    spread=m["spread"],
                    expiration_date=m["expiration_date"],
                    is_active=True
                )
                session.add(db_m)
            db_markets.append(db_m)
            
        await session.commit()
        
        # Reload markets with actual IDs
        m_stmt = select(Market).where(Market.is_active == True)
        m_result = await session.execute(m_stmt)
        active_db_markets = m_result.scalars().all()
        
        # 5. Process each active market
        trades_executed = 0
        for market in active_db_markets:
            # Check if we already have a position in this market to avoid duplicate trades
            pos_stmt = select(Position).where(Position.market_id == market.id)
            pos_result = await session.execute(pos_stmt)
            existing_pos = pos_result.scalar_one_or_none()
            
            if existing_pos:
                logger.info(f"Supervisor: Position already open for {market.slug}. Skipping prediction/trade loop.")
                continue
                
            city = [c for c in cities if c.id == market.city_id][0]
            
            # Step A: Weather Intel Agent (Agent 1)
            weather_res = await self.weather_intel.analyze_city(city.name, city.latitude, city.longitude)
            
            # Step B: Local Research Agent (Agent 2)
            local_res = await self.local_research.research_local_agency(
                city.name, city.country, city.latitude, city.longitude, city.local_agency
            )
            
            # Step C: Market Agent (Agent 3)
            # Find markets list format
            market_dict_list = [{
                "id": market.id,
                "city_id": market.city_id,
                "title": market.title,
                "slug": market.slug,
                "yes_price": market.yes_price,
                "no_price": market.no_price,
                "volume": market.volume,
                "liquidity": market.liquidity,
                "spread": market.spread
            }]
            market_res = await self.market_agent.analyze_markets(city.id, city.name, market_dict_list)
            
            # Step D: Research Agent (Agent 4)
            research_res = await self.research_agent.perform_research(city.name)
            
            # Get climatology prior (from 10 years of archives)
            climatology_prior = await self._fetch_climatology_prior(city.latitude, city.longitude)
            
            # Step E: Prediction Agent (Agent 5)
            pred_res = await self.prediction_agent.generate_prediction(
                city_name=city.name,
                weather_summary=weather_res["summary"],
                local_summary=local_res["analysis"],
                research_summary=research_res["summary"],
                sentiment_score=research_res["sentiment_score"],
                market=market_dict_list[0],
                climatology_prior=climatology_prior
            )
            
            # Save Prediction to DB
            pred_db = Prediction(
                market_id=market.id,
                prediction_date=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
                model_probability_yes=pred_res["probability_yes"],
                model_probability_no=pred_res["probability_no"],
                confidence=pred_res["confidence"],
                edge=pred_res["edge"],
                expected_value=pred_res["expected_value"],
                decision=pred_res["decision"],
                reasoning=pred_res["reasoning"]
            )
            session.add(pred_db)
            await session.flush()
            
            # Save Weather & Research results to DB
            weather_db = WeatherData(
                city_id=city.id,
                date=datetime.utcnow().strftime("%Y-%m-%d"),
                precipitation_probability=pred_res["probability_yes"] * 100.0,
                extreme_alerts=local_res["forecast_summary"]
            )
            session.add(weather_db)
            
            research_db = ResearchResult(
                city_id=city.id,
                date=datetime.utcnow().strftime("%Y-%m-%d"),
                sentiment_score=research_res["sentiment_score"],
                ai_summary=research_res["summary"],
                sources=",".join(research_res.get("sources", [])),
                confidence_score=research_res["confidence"]
            )
            session.add(research_db)
            
            # Step F: Risk Agent (Agent 6)
            risk_res = await self.risk_agent.evaluate_trade(
                city_name=city.name,
                decision=pred_res["decision"],
                model_prob=pred_res["probability_yes"],
                market_price=market.yes_price,
                portfolio_value=portfolio_value,
                current_exposure=exposure,
                daily_pnl=daily_pnl
            )
            
            # Step G: Execution Agent (Agent 7)
            if risk_res["status"] == "APPROVED" and risk_res["allocated_dollars"] > 0:
                side = "YES" if "YES" in pred_res["decision"] else "NO"
                exec_res = await self.execution_agent.execute_trade(
                    session=session,
                    market=market,
                    side=side,
                    cost_dollars=risk_res["allocated_dollars"],
                    reason=pred_res["reasoning"]
                )
                if exec_res["success"]:
                    trades_executed += 1
                    # Update exposure
                    exposure += risk_res["allocated_dollars"]
                    cash -= risk_res["allocated_dollars"]
                    
        # 6. Hedging Agent (Agent 9)
        # Fetch current open positions
        pos_stmt = select(Position)
        pos_result = await session.execute(pos_stmt)
        active_positions = pos_result.scalars().all()
        positions_list = []
        for p in active_positions:
            m_stmt = select(Market).where(Market.id == p.market_id)
            m_result = await session.execute(m_stmt)
            m = m_result.scalar_one_or_none()
            if m:
                c_stmt = select(City).where(City.id == m.city_id)
                c_result = await session.execute(c_stmt)
                c = c_result.scalar_one_or_none()
                positions_list.append({
                    "id": p.id,
                    "market_id": p.market_id,
                    "side": p.side,
                    "shares": p.shares,
                    "average_price": p.average_price,
                    "current_price": p.current_price,
                    "city_name": c.name if c else ""
                })
                
        # Generate markets dict format for hedging agent
        available_markets_list = []
        for m in active_db_markets:
            c_stmt = select(City).where(City.id == m.city_id)
            c_result = await session.execute(c_stmt)
            c = c_result.scalar_one_or_none()
            available_markets_list.append({
                "id": m.id,
                "slug": m.slug,
                "yes_price": m.yes_price,
                "no_price": m.no_price,
                "city_name": c.name if c else ""
            })
            
        hedges = await self.hedging_agent.check_hedges(
            session=session,
            active_positions=positions_list,
            available_markets=available_markets_list,
            portfolio_value=portfolio_value
        )
        
        # Execute hedges
        for h in hedges:
            h_market_stmt = select(Market).where(Market.id == h["market_id"])
            h_market_result = await session.execute(h_market_stmt)
            h_market = h_market_result.scalar_one_or_none()
            if h_market:
                await self.execution_agent.execute_trade(
                    session=session,
                    market=h_market,
                    side=h["side"],
                    cost_dollars=h["cost"],
                    reason=h["reason"]
                )
                
        # 7. Update Portfolio State final revaluation
        final_port_state = await self.portfolio_agent.generate_portfolio_report(session)
        
        await session.commit()
        logger.info(f"Supervisor Agent: Workflow cycle completed. Trades executed: {trades_executed}")
        
        # Send Telegram report
        msg = (
            f"🔔 *Weather AI Agent Cycle Completed*\n\n"
            f"📈 *Trades Executed:* {trades_executed}\n"
            f"🛡️ *Hedges Executed:* {len(hedges)}\n"
            f"💰 *Portfolio Value:* ${final_port_state['portfolio_value']:.2f}\n"
            f"💵 *Available Cash:* ${final_port_state['cash']:.2f}\n"
            f"📊 *Unrealized PnL:* ${final_port_state.get('unrealized_pnl', 0.0):.2f}\n"
        )
        try:
            await self.telegram.send_message(msg)
        except Exception as te:
            logger.error(f"Failed to send telegram message: {te}")

        return {
            "success": True,
            "trades_executed": trades_executed,
            "hedges_executed": len(hedges),
            "portfolio_value": final_port_state["portfolio_value"],
            "cash": final_port_state["cash"]
        }


    async def _fetch_climatology_prior(self, lat: float, lon: float) -> float:
        """Fetch historical archive and calculate baseline prior probability of rain"""
        end_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")  # 5 years of history
        
        archive_data = await self.open_meteo.get_historical_climatology(lat, lon, start_date, end_date)
        return self.prediction_agent.model.calculate_climatology_prior(archive_data)

    async def _settle_expired_contracts(self, session: AsyncSession, cities: List[City]):
        """Query actual historical weather outcomes and resolve expired contract positions"""
        # Fetch open positions
        pos_stmt = select(Position)
        pos_result = await session.execute(pos_stmt)
        positions = pos_result.scalars().all()
        
        if not positions:
            return
            
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        market_resolutions = {}
        for pos in positions:
            m_stmt = select(Market).where(Market.id == pos.market_id)
            m_result = await session.execute(m_stmt)
            market = m_result.scalar_one_or_none()
            
            # Settle if market expiration date is past or equal to today
            if market and market.is_active and market.expiration_date <= today:
                city = [c for c in cities if c.id == market.city_id][0]
                
                # Fetch actual recorded weather data for the expiration date
                archive = await self.open_meteo.get_historical_climatology(
                    city.latitude, city.longitude, market.expiration_date, market.expiration_date
                )
                
                resolved_side = "NO"
                if archive and "daily" in archive and "precipitation_sum" in archive["daily"]:
                    precip = archive["daily"]["precipitation_sum"]
                    # If it rained on that date (> 0.1 mm), YES wins, otherwise NO wins
                    if len(precip) > 0 and precip[0] is not None and precip[0] > 0.1:
                        resolved_side = "YES"
                        
                # Temperature contract resolution
                if "exceed" in market.title.lower():
                    resolved_side = "NO"
                    if archive and "daily" in archive and "temperature_2m_max" in archive["daily"]:
                        temp_max = archive["daily"]["temperature_2m_max"]
                        # extract threshold from title
                        import re
                        match = re.search(r"exceed (\d+(\.\d+)?)", market.title.lower())
                        if match and len(temp_max) > 0 and temp_max[0] is not None:
                            threshold = float(match.group(1))
                            if temp_max[0] > threshold:
                                resolved_side = "YES"
                                
                market_resolutions[market.slug] = resolved_side
                
        if market_resolutions:
            logger.info(f"Supervisor: Settling expired contracts: {market_resolutions}")
            await self.execution_agent.trader.resolve_expired_markets(session, market_resolutions)
