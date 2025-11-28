from sqlalchemy.orm import Session
from app.models.ubicacion import Ubicacion
from app.schemas.ubicacion import UbicacionCreate

def create_ubicacion(db: Session, ubicacion: UbicacionCreate):
    db_ubicacion = Ubicacion(
        nombre=ubicacion.nombre,
        tipo=ubicacion.tipo,
        edificio_id=ubicacion.edificio_id,
        latitud=ubicacion.latitud,
        longitud=ubicacion.longitud,
        piso=ubicacion.piso
    )
    db.add(db_ubicacion)
    db.commit()
    db.refresh(db_ubicacion)
    return db_ubicacion

def get_ubicacion_by_id(db: Session, id: int):
    return db.query(Ubicacion).filter(Ubicacion.id == id).first()

def get_all_ubicaciones(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Ubicacion).offset(skip).limit(limit).all()
