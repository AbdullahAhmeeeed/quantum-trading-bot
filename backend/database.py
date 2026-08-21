from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from models import Base

# High-Concurrency Institutional SQLite Configuration with WAL Mode
SQLALCHEMY_DATABASE_URL = "sqlite:///./trading_bot.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30.0}
)

# Enable Write-Ahead Logging (WAL) and fast synchronization for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
