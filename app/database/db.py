from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config.settings import settings

# A longer pool timeout + SQLite busy handling avoids "database is locked" errors when
# the dashboard reads while a workflow cycle writes concurrently.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"timeout": 30} if settings.database_url.startswith("sqlite") else {},
)

# Enable Write-Ahead Logging so readers don't block the writer (and vice-versa),
# and set a busy timeout so concurrent writes wait instead of failing immediately.
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db_context():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
