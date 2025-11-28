from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.schemas.ubicacion import UbicacionCreate, UbicacionOut
from app.crud import crud_ubicacion
from app.db.session import get_db 

router = APIRouter()

@router.post("/ubicaciones", response_model=UbicacionOut)
def create_ubicacion(ubicacion: UbicacionCreate, db: Session = Depends(get_db)):
    return crud_ubicacion.create_ubicacion(db, ubicacion)

@router.get("/ubicaciones/{id}", response_model=UbicacionOut)
def get_ubicacion(id: int, db: Session = Depends(get_db)):
    ubicacion = crud_ubicacion.get_ubicacion_by_id(db, id)
    if not ubicacion:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")
    return ubicacion

@router.get("/ubicaciones", response_model=List[UbicacionOut])
def list_ubicaciones(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_ubicacion.get_all_ubicaciones(db, skip, limit)
