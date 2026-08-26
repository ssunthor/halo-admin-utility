import logging
from typing import Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from core.database.models import Base

logger = logging.getLogger(__name__)

_write_engine = None
_read_engine = None
_WriteSessionFactory = None
_ReadSessionFactory = None

def initialize_database(config: Dict[str, Any]):
    global _write_engine, _read_engine, _WriteSessionFactory, _ReadSessionFactory
    if _write_engine and _read_engine:
        return

    db_config = config.get('database', {})
    write_dsn = db_config.get('write_dsn')
    read_dsn = db_config.get('read_dsn')

    if not write_dsn and db_config.get('dsn'):
        write_dsn = db_config.get('dsn')
        read_dsn = db_config.get('dsn')

    if not write_dsn or not read_dsn:
        logger.critical("Database read/write DSNs not found in configuration.")
        raise ValueError("Database read/write DSNs are not configured.")

    try:
        _write_engine = create_engine(
            write_dsn, 
            pool_pre_ping=True,
            pool_size=10, 
            max_overflow=20
        )
        _WriteSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_write_engine)
        
        _read_engine = create_engine(
            read_dsn, 
            pool_pre_ping=True,
            pool_size=10, 
            max_overflow=20
        )
        _ReadSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_read_engine)
        
        logger.info("Database initialized with separate read and write engines.")
    except Exception as e:
        logger.critical(f"DB Initialization failed: {e}", exc_info=True)
        raise

@contextmanager
def get_db_session(*args, read_only: bool = False, **kwargs):
    factory = _ReadSessionFactory if read_only else _WriteSessionFactory
    
    if not factory:
        logger.critical("Database session factory is not initialized.")
        raise RuntimeError("Database not initialized. Call initialize_database first.")
    
    session = factory()
    try:
        yield session
        if not read_only:
            session.commit()
    except Exception as e:
        logger.error(f"Error during DB session, rolling back: {e}", exc_info=True)
        if not read_only:
            session.rollback()
        raise
    finally:
        session.close()

def init_db():
    if not _write_engine:
        raise RuntimeError("Database not initialized.")
    Base.metadata.create_all(bind=_write_engine)

def reset_db():
    if not _write_engine:
        raise RuntimeError("Database not initialized.")
    Base.metadata.drop_all(bind=_write_engine)
    Base.metadata.create_all(bind=_write_engine)