from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.schemas.edificio import EdificioCreate, EdificioOut
from app.crud import crud_edificio
from app.db.session import get_db 

router = APIRouter()

@router.post("/edificios", response_model=EdificioOut)
def create_edificio(edificio: EdificioCreate, db: Session = Depends(get_db)):
    return crud_edificio.create_edificio(db, edificio)

@router.get("/edificios/{id}", response_model=EdificioOut)
def get_edificio(id: int, db: Session = Depends(get_db)):
    edificio = crud_edificio.get_edificio_by_id(db, id)
    if not edificio:
        raise HTTPException(status_code=404, detail="Edificio no encontrado")
    return edificio

@router.get("/edificios", response_model=List[EdificioOut])
def list_edificios(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_edificio.get_all_edificios(db, skip, limit)
