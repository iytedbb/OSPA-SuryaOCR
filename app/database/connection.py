"""
Database connection and session management for SuryaOCR
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('DB_PORT', '5433')
DB_USER = os.getenv('DB_USER', 'admin')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'ospa_suryaocr')

if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD environment variable is required")

# Database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy setup
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False
    # echo=os.getenv('DEBUG', 'False').lower() == 'true'
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db() -> Session:
    """
    Get database session
    Use this function to get database session in your routes
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_database_if_not_exists():
    """
    Create database if it doesn't exist
    Call this function before creating tables
    """
    try:
        # Create a connection without specifying database name
        temp_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
        temp_engine = create_engine(temp_url, isolation_level='AUTOCOMMIT')

        with temp_engine.connect() as conn:
            # Check if database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_catalog.pg_database WHERE datname = :db_name"),
                {"db_name": DB_NAME}
            )

            if not result.fetchone():
                logger.info(f"Creating database: {DB_NAME}")
                conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
                logger.info(f"Database {DB_NAME} created successfully")
            else:
                logger.info(f"Database {DB_NAME} already exists")

        temp_engine.dispose()

    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise


def create_tables():
    """
    Create all database tables
    """
    try:
        # Import models to register them with Base
        import sys
        import os

        # Add current directory to path for imports
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)

        # Import models module
        import models

        logger.info("Creating database tables...")

        # Use the Base from models module
        models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

    except ImportError as e:
        logger.warning(f"Models module not found: {e}. Skipping table creation.")
        logger.info("You need to create models.py first")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise


def check_database_connection():
    """
    Test database connection
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def initialize_database():
    """
    Initialize the complete database setup
    Call this function when starting your application
    """
    try:
        logger.info("Initializing database...")

        # Step 1: Create database if it doesn't exist
        create_database_if_not_exists()

        # Step 2: Test connection
        if not check_database_connection():
            raise Exception("Failed to connect to database")

        # Step 3: Create tables
        create_tables()

        # Step 4: Enable UUID extension
        with engine.connect() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            conn.commit()

        logger.info("Database initialization completed successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


if __name__ == "__main__":
    # Test script
    print("Testing database connection...")
    initialize_database()
    print("Database setup completed successfully!")