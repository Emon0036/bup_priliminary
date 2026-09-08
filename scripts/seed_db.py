import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.database import SessionLocal, engine
from backend.models import Agent, SimulationRun, Location, Job, Product
from backend.simulation.engine import make_citizens
def main():
    if not engine or not SessionLocal: raise SystemExit("DATABASE_URL is not set. Configure a TiDB Cloud Starter URL before seeding.")
    db=SessionLocal()
    try:
        if db.query(Agent).count(): print("Seed skipped: agents already exist."); return
        db.add(SimulationRun(name="Synthetic demo baseline",seed=42,current_month=0,status="ACTIVE"))
        for name,kind,x,y in [("Housing","HOUSE",4,4),("Workplace","WORKPLACE",22,5),("Market","MARKET",22,22),("Bank","BANK",8,22),("School","SCHOOL",5,15),("City Center","CITY_CENTER",15,15)]: db.add(Location(name=name,location_type=kind,x=x,y=y,capacity=500))
        for title,skill,salary,cap in [("Service Assistant","LOW",22000,80),("Technician","MEDIUM",35000,60),("Analyst","HIGH",60000,30)]: db.add(Job(title=title,industry="Synthetic",required_skill=skill,monthly_salary=salary,capacity=cap,filled_positions=0,location_x=22,location_y=5,active=True))
        for name,cat,price,essential,unit in [("Rice","FOOD",70,True,"kg"),("Vegetables","FOOD",80,True,"kg"),("Cooking Oil","FOOD",190,True,"litre"),("Fish","FOOD",350,True,"kg"),("Transport","TRANSPORT",40,True,"trip"),("Rent","HOUSING",9000,True,"month"),("Utilities","HOUSING",2500,True,"month"),("Internet","OTHER",1000,False,"month")]: db.add(Product(name=name,category=cat,base_price=price,current_price=price,essential=essential,unit=unit))
        for c in make_citizens(): db.add(Agent(agent_code=c.code,name=c.name,age=c.age,area_type="URBAN",occupation=c.occupation,industry="Synthetic",skill_level=c.skill_level,employment_status=c.employment_status,family_size=c.family_size,base_monthly_income=c.income,base_food_expense=c.food,base_housing_expense=c.housing,base_transport_expense=c.transport,base_other_expense=c.other,initial_savings=c.savings,initial_debt=c.debt,goal=c.goal,goal_amount=50000,home_x=c.x,home_y=c.y))
        db.commit(); print("Seeded 500 synthetic agents, locations, jobs, products, and baseline run.")
    finally: db.close()
if __name__=="__main__": main()
