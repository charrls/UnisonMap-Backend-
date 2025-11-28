from sqlalchemy.orm import Session
from app.models.edificio import Edificio
from app.schemas.edificio import EdificioCreate

def create_edificio(db: Session, edificio: EdificioCreate):
    db_edificio = Edificio(
        nombre=edificio.nombre,
        descripcion=edificio.descripcion
    )
    db.add(db_edificio)
    db.commit()
    db.refresh(db_edificio)
    return db_edificio

def get_edificio_by_id(db: Session, id: int):
    return db.query(Edificio).filter(Edificio.id == id).first()

def get_all_edificios(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Edificio).offset(skip).limit(limit).all()
