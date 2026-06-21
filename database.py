import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database file path
DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "church.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Connect args needed for SQLite to allow multiple threads to access it
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
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
