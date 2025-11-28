from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Conexion(Base):
    __tablename__ = "conexiones"

    id = Column(Integer, primary_key=True, index=True)

    origen_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=False)
    destino_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=False)

    peso = Column(Float, nullable=False)

    origen = relationship("Ubicacion", foreign_keys=[origen_id], backref="conexiones_salida")
    destino = relationship("Ubicacion", foreign_keys=[destino_id], backref="conexiones_entrada")
