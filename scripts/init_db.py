from backend.database import Base, engine
def main():
    if not engine: raise SystemExit("DATABASE_URL is not set. Configure a TiDB Cloud Starter URL before database initialization.")
    print("Creating TiDB/MySQL-compatible schema..."); Base.metadata.create_all(engine); print("Schema ready.")
if __name__=="__main__": main()
