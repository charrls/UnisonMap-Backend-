from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.schemas.conexion import ConexionCreate, ConexionOut
from app.crud import crud_conexion
from app.db.session import get_db 

router = APIRouter()

@router.post("/conexiones", response_model=ConexionOut)
def create_conexion(conexion: ConexionCreate, db: Session = Depends(get_db)):
    return crud_conexion.create_conexion(db, conexion)

@router.get("/conexiones/{id}", response_model=ConexionOut)
def get_conexion(id: int, db: Session = Depends(get_db)):
    conexion = crud_conexion.get_conexion_by_id(db, id)
    if not conexion:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")
    return conexion

@router.get("/conexiones", response_model=List[ConexionOut])
def list_conexiones(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_conexion.get_all_conexiones(db, skip, limit)
