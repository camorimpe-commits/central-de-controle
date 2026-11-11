from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
from core.data_processor import data_processor

router = APIRouter(prefix="/api/decisions", tags=["decisions"])

class SimulationRequest(BaseModel):
    sla_improvement_pct: float
    cost_reduction_pct: float
    year: Optional[int] = None

@router.get("/insights")
def get_insights(
    year: Optional[int] = Query(None),
    month: Optional[str] = Query(None),
    tema: Optional[str] = Query(None)
):
    return data_processor.generate_decision_insights(year, month, tema)

@router.post("/simulate")
def simulate(req: SimulationRequest):
    return data_processor.simulate_what_if(
        sla_improvement_pct=req.sla_improvement_pct,
        cost_reduction_pct=req.cost_reduction_pct,
        year=req.year
    )
