from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from .config import DATABASE_URL

class Base(DeclarativeBase): pass

def get_engine():
    if not DATABASE_URL: return None
    # TiDB connection strings are commonly supplied as mysql://; use the
    # declared pure-Python PyMySQL driver instead of relying on MySQLdb.
    database_url = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1) if DATABASE_URL.startswith("mysql://") else DATABASE_URL
    options = {"pool_pre_ping": True, "poolclass": NullPool}
    if "tidbcloud" in database_url or "ssl" in database_url: options["connect_args"] = {"ssl": {}}
    return create_engine(database_url, **options)

engine = get_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False) if engine else None
