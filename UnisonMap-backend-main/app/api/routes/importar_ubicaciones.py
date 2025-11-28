from fastapi import APIRouter
from app.scripts.import_ubicaciones import importar_csv

router = APIRouter()

@router.post("/api/importar_ubicaciones")
def importar_ubicaciones_endpoint():
    try:
        importar_csv("app/scripts/ubicacionesdpting.csv")
        return {"status": "Importación completada correctamente."}
    except Exception as e:
        return {"status": "Error durante la importación.", "detalle": str(e)}

