from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any
from core.data_processor import data_processor

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("/options")
def get_options():
    return data_processor.get_filter_options()

@router.get("/summary")
def get_summary(
    year: Optional[int] = Query(None),
    month: Optional[str] = Query(None),
    tema: Optional[str] = Query(None)
):
    return data_processor.get_summary_kpis(year, month, tema)

@router.get("/trends")
def get_trends(
    year: Optional[int] = Query(None),
    tema: Optional[str] = Query(None)
):
    return data_processor.get_monthly_trends(year, tema)

@router.get("/pareto")
def get_pareto(
    year: Optional[int] = Query(None),
    month: Optional[str] = Query(None),
    top_n: int = Query(10, ge=3, le=30)
):
    return data_processor.get_thematic_pareto(year, month, top_n)

@router.get("/rankings")
def get_rankings(
    year: Optional[int] = Query(None),
    month: Optional[str] = Query(None),
    tema: Optional[str] = Query(None),
    limit: int = Query(35, ge=5, le=100)
):
    return data_processor.get_credor_rankings(year, month, tema, limit)

@router.get("/deviations")
def get_deviations(
    year: Optional[int] = Query(None),
    month: Optional[str] = Query(None),
    tema: Optional[str] = Query(None)
):
    return data_processor.get_deviations_and_anomalies(year, month, tema)
