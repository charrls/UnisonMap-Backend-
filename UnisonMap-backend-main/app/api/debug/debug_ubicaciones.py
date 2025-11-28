from app.db.session import SessionLocal
from app.models.ubicacion import Ubicacion

def verificar_ubicaciones():
    db = SessionLocal()
    try:
        ubicacion1 = db.query(Ubicacion).filter(Ubicacion.id == 1).first()
        ubicacion2 = db.query(Ubicacion).filter(Ubicacion.id == 2).first()
        
        print(f"Ubicación ID 1: {ubicacion1}")
        if ubicacion1:
            print(f"  - Nombre: {ubicacion1.nombre}")
            print(f"  - Coordenadas: {ubicacion1.latitud}, {ubicacion1.longitud}")
        
        print(f"Ubicación ID 2: {ubicacion2}")
        if ubicacion2:
            print(f"  - Nombre: {ubicacion2.nombre}")
            print(f"  - Coordenadas: {ubicacion2.latitud}, {ubicacion2.longitud}")
            
        todas_ubicaciones = db.query(Ubicacion).all()
        print(f"\nTotal de ubicaciones en BD: {len(todas_ubicaciones)}")
        for ub in todas_ubicaciones:
            print(f"  ID {ub.id}: {ub.nombre} ({ub.latitud}, {ub.longitud})")
            
    finally:
        db.close()

if __name__ == "__main__":
    verificar_ubicaciones()