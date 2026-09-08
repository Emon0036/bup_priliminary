import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.simulation.engine import make_citizens
def main():
    p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=500); p.add_argument("--seed",type=int,default=42); args=p.parse_args(); print(json.dumps([c.snapshot(0) for c in make_citizens(args.count,args.seed)],indent=2))
if __name__=="__main__": main()
