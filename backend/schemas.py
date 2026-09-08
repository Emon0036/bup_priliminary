from pydantic import BaseModel, Field
from typing import Literal
class SimulationRequest(BaseModel): simulation_run_id:int=1; months:int=Field(ge=1,le=24)
class EventRequest(BaseModel): event_type:Literal["FOOD_PRICE_SHOCK","GENERAL_INFLATION","TAX_CHANGE","JOB_SHORTAGE","SALARY_CHANGE"]; magnitude:float=Field(gt=-100,le=300); duration_months:int=Field(ge=1,le=24); target:str="ALL"
class PathRequest(BaseModel): start:tuple[int,int]; goal:tuple[int,int]
