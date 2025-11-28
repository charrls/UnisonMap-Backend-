from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class TipoUbicacionEnum(str, enum.Enum):
    aula = "aula"
    oficina = "oficina"
    baño = "baño"
    cafeteria = "cafeteria"
    entrada = "entrada"
    pasillo = "pasillo"
    laboratorio = "laboratorio"
    edificio = "edificio"
    otro = "otro"

class Ubicacion(Base):
    __tablename__ = "ubicaciones"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    tipo = Column(Enum(TipoUbicacionEnum), nullable=False)

    edificio_id = Column(Integer, ForeignKey("edificios.id"))
    edificio = relationship("Edificio", back_populates="ubicaciones")

    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    piso = Column(Integer, default=1, nullable=False)

