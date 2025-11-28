from sqlalchemy.orm import Session
from app.models.conexion import Conexion
from app.schemas.conexion import ConexionCreate

def create_conexion(db: Session, conexion: ConexionCreate):
    db_conexion = Conexion(
        origen_id=conexion.origen_id,
        destino_id=conexion.destino_id,
        peso=conexion.peso
    )
    db.add(db_conexion)
    db.commit()
    db.refresh(db_conexion)
    return db_conexion

def get_conexion_by_id(db: Session, id: int):
    return db.query(Conexion).filter(Conexion.id == id).first()

def get_all_conexiones(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Conexion).offset(skip).limit(limit).all()
