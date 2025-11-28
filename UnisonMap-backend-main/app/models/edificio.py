from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Edificio(Base):
    __tablename__ = "edificios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False, unique=True)
    descripcion = Column(String)

    ubicaciones = relationship("Ubicacion", back_populates="edificio")
