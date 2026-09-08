import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.database import Base, engine
import backend.models  # Registers every mapped table before create_all.
def main():
    if not engine: raise SystemExit("DATABASE_URL is not set. Configure a TiDB Cloud Starter URL before database initialization.")
    print("Creating TiDB/MySQL-compatible schema..."); Base.metadata.create_all(engine); print("Schema ready.")
if __name__=="__main__": main()
