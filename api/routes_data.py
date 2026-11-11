import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from core.config import UPLOADS_DIR, DATA_DIR
from core.data_processor import data_processor

router = APIRouter(prefix="/api/data", tags=["data"])

@router.get("/status")
def get_data_status():
    return {
        "total_records": data_processor.total_records,
        "last_updated": data_processor.last_updated,
        "source": data_processor.data_source,
        "is_processing": data_processor.is_processing
    }

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a new CSV or Excel dataset, process immediately and update dashboard."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(
            status_code=400,
            detail="Formato inválido! Envie apenas arquivos no formato .csv, .xlsx ou .xls."
        )

    # Save to uploads directory
    target_path = UPLOADS_DIR / file.filename
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Process immediately
        res = data_processor.import_uploaded_file(target_path, file.filename)
        if not res.get("success"):
            raise HTTPException(status_code=500, detail=res.get("error", "Falha no processamento"))
            
        return {
            "success": True,
            "message": f"Arquivo '{file.filename}' processado com sucesso!",
            "records": data_processor.total_records,
            "last_updated": data_processor.last_updated,
            "source": f"Upload: {file.filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {str(e)}")

@router.post("/sync-google-sheets")
def sync_google_sheets():
    """Trigger on-demand fetch and sync from the configured online Google Sheet."""
    res = data_processor.sync_from_google_sheets()
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Falha na sincronização"))
    return {
        "success": True,
        "message": "Sincronização com o Google Sheets concluída com sucesso!",
        "records": data_processor.total_records,
        "last_updated": data_processor.last_updated,
        "source": res.get("source")
    }

@router.get("/export")
def export_data(format: str = "csv"):
    """Export current rankings dataset as CSV."""
    rankings = data_processor.get_credor_rankings(limit=200)
    import pandas as pd
    import io
    
    df_exp = pd.DataFrame(rankings)
    if format == "json":
        return rankings
        
    output = io.StringIO()
    df_exp.to_csv(output, index=False, sep=';', encoding='utf-8-sig')
    csv_bytes = output.getvalue().encode('utf-8-sig')
    
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=relatorio_eficiencia_operacional.csv"}
    )
