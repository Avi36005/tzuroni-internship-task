from datetime import datetime
from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.db import Base

class City(Base):
    __tablename__ = "cities"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    local_agency: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Relationships
    weather_records = relationship("WeatherData", back_populates="city", cascade="all, delete-orphan")
    research_records = relationship("ResearchResult", back_populates="city", cascade="all, delete-orphan")
    markets = relationship("Market", back_populates="city", cascade="all, delete-orphan")

class WeatherData(Base):
    __tablename__ = "weather_data"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(Integer, ForeignKey("cities.id"), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    
    temperature_max: Mapped[float] = mapped_column(Float, nullable=True)
    temperature_min: Mapped[float] = mapped_column(Float, nullable=True)
    precipitation_sum: Mapped[float] = mapped_column(Float, nullable=True)
    precipitation_probability: Mapped[float] = mapped_column(Float, nullable=True)
    humidity_mean: Mapped[float] = mapped_column(Float, nullable=True)
    wind_speed_max: Mapped[float] = mapped_column(Float, nullable=True)
    pressure_mean: Mapped[float] = mapped_column(Float, nullable=True)
    uv_index_max: Mapped[float] = mapped_column(Float, nullable=True)
    extreme_alerts: Mapped[str] = mapped_column(Text, nullable=True)
    
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    city = relationship("City", back_populates="weather_records")

class ResearchResult(Base):
    __tablename__ = "research_results"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(Integer, ForeignKey("cities.id"), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str] = mapped_column(Text, nullable=True)  # JSON list of URLs
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    city = relationship("City", back_populates="research_records")

class Market(Base):
    __tablename__ = "markets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(Integer, ForeignKey("cities.id"), nullable=False)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    condition_id: Mapped[str] = mapped_column(String(255), nullable=True)
    clob_token_id_yes: Mapped[str] = mapped_column(String(255), nullable=True)
    clob_token_id_no: Mapped[str] = mapped_column(String(255), nullable=True)
    
    yes_price: Mapped[float] = mapped_column(Float, nullable=False)
    no_price: Mapped[float] = mapped_column(Float, nullable=False)
    implied_probability: Mapped[float] = mapped_column(Float, nullable=False)
    
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    spread: Mapped[float] = mapped_column(Float, default=0.01)
    
    expiration_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    city = relationship("City", back_populates="markets")
    predictions = relationship("Prediction", back_populates="market", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="market", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="market", cascade="all, delete-orphan")

class Prediction(Base):
    __tablename__ = "predictions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[int] = mapped_column(Integer, ForeignKey("markets.id"), nullable=False)
    prediction_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    
    model_probability_yes: Mapped[float] = mapped_column(Float, nullable=False)
    model_probability_no: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    edge: Mapped[float] = mapped_column(Float, nullable=False)
    expected_value: Mapped[float] = mapped_column(Float, nullable=False)
    
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # BUY YES, BUY NO, NO TRADE
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    market = relationship("Market", back_populates="predictions")
    orders = relationship("Order", back_populates="prediction")

class Order(Base):
    __tablename__ = "orders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[int] = mapped_column(Integer, ForeignKey("markets.id"), nullable=False)
    prediction_id: Mapped[int] = mapped_column(Integer, ForeignKey("predictions.id"), nullable=True)
    
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # YES or NO
    price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)  # Number of shares
    cost: Mapped[float] = mapped_column(Float, nullable=False)    # In cash
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING, FILLED, CANCELLED
    slippage: Mapped[float] = mapped_column(Float, default=0.0)
    
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    market = relationship("Market", back_populates="orders")
    prediction = relationship("Prediction", back_populates="orders")

class Position(Base):
    __tablename__ = "positions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[int] = mapped_column(Integer, ForeignKey("markets.id"), nullable=False)
    
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # YES or NO
    average_price: Mapped[float] = mapped_column(Float, nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    
    is_hedged: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    market = relationship("Market", back_populates="positions")

class PortfolioState(Base):
    __tablename__ = "portfolio_state"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    portfolio_value: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    daily_return: Mapped[float] = mapped_column(Float, default=0.0)
    exposure: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
