import csv
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.edificio import Edificio
from app.models.ubicacion import Ubicacion

def importar_csv(path_csv):  # Aquí va un nombre de parámetro, no una cadena
    db: Session = SessionLocal()

    with open(path_csv, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            nombre_edificio = row['edificio'].strip()

            # Buscar o crear edificio
            edificio = db.query(Edificio).filter_by(nombre=nombre_edificio).first()
            if not edificio:
                edificio = Edificio(nombre=nombre_edificio, descripcion="")
                db.add(edificio)
                db.commit()
                db.refresh(edificio)

            # Crear ubicación asociada
            ubicacion = Ubicacion(
                nombre=row['nombre'].strip(),
                tipo=row['tipo'].strip(),
                edificio_id=edificio.id,
                latitud=float(row['latitud']),
                longitud=float(row['longitud']),
                piso=int(row['piso']),
            )
            db.add(ubicacion)

        db.commit()
    print("Importación completada.")

# Llamada a la función con el nombre del archivo CSV
if __name__ == '__main__':
    importar_csv("app/scripts/ubicacionesdpting.csv")

