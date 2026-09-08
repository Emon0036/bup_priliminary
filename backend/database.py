from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from .config import DATABASE_URL

class Base(DeclarativeBase): pass

def get_engine():
    if not DATABASE_URL: return None
    options = {"pool_pre_ping": True, "poolclass": NullPool}
    if "tidbcloud" in DATABASE_URL or "ssl" in DATABASE_URL: options["connect_args"] = {"ssl": {}}
    return create_engine(DATABASE_URL, **options)

engine = get_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False) if engine else None
