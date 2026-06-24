import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Check if DATABASE_URL environment variable is provided (e.g. by Render/Supabase)
ENV_DB_URL = os.environ.get("DATABASE_URL")

if ENV_DB_URL:
    # Heroku and Render sometimes use postgres:// instead of postgresql://
    if ENV_DB_URL.startswith("postgres://"):
        ENV_DB_URL = ENV_DB_URL.replace("postgres://", "postgresql://", 1)
    DATABASE_URL = ENV_DB_URL
    connect_args = {}
else:
    DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "church.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    connect_args = {"check_same_thread": False}

# Connect args needed for SQLite to allow multiple threads to access it, not needed for Postgres
engine = create_engine(
    DATABASE_URL, connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
