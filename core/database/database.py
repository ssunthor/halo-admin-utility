from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database.models import Base

def get_engine(dsn: str):
    return create_engine(dsn, pool_pre_ping=True, pool_size=10, max_overflow=20)

def get_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(engine):
    Base.metadata.create_all(bind=engine)

def reset_db(engine):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)