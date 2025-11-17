from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.core.config import settings

# Handle both SQLite (local) and PostgreSQL (Render)
# PostgreSQL URLs from Render need to be used as-is
database_url = settings.DATABASE_URL
if database_url.startswith("postgres://"):
    # Render uses postgres:// but SQLAlchemy 2.0 needs postgresql://
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
