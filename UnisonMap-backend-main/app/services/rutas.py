from sqlalchemy.orm import Session
from app.models.ubicacion import Ubicacion
from app.models.conexion import Conexion
import heapq

def construir_grafo(db: Session):
    ubicaciones = db.query(Ubicacion).all()
    conexiones = db.query(Conexion).all()

    grafo = {u.id: [] for u in ubicaciones}

    for conexion in conexiones:
        grafo[conexion.origen_id].append((conexion.destino_id, conexion.peso))
    return grafo

def dijkstra(grafo, inicio, destino):
    distancias = {nodo: float("inf") for nodo in grafo}
    distancias[inicio] = 0

    anterior = {}
    cola = [(0, inicio)]

    while cola:
        actual_dist, actual_nodo = heapq.heappop(cola)

        if actual_nodo == destino:
            break

        for vecino, peso in grafo[actual_nodo]:
            distancia = actual_dist + peso
            if distancia < distancias[vecino]:
                distancias[vecino] = distancia
                anterior[vecino] = actual_nodo
                heapq.heappush(cola, (distancia, vecino))

    ruta = []
    actual = destino
    while actual in anterior:
        ruta.insert(0, actual)
        actual = anterior[actual]
    if actual == inicio:
        ruta.insert(0, inicio)
        return ruta
    return []


def obtener_ruta(db: Session, desde_id: int, hacia_id: int):
    grafo = construir_grafo(db)
    ruta_ids = dijkstra(grafo, desde_id, hacia_id)

    if not ruta_ids:
        return []

    ubicaciones = db.query(Ubicacion).filter(Ubicacion.id.in_(ruta_ids)).all()
    ubicaciones_dict = {u.id: u for u in ubicaciones}
    ruta_ordenada = [ubicaciones_dict[i] for i in ruta_ids]
    return ruta_ordenada


def calcular_distancia_real(ubicacion1, ubicacion2):
    """
    Calcula distancia real entre dos puntos usando fórmula de Haversine
    """
    from math import radians, cos, sin, asin, sqrt
    
    lat1, lon1 = radians(ubicacion1.latitud), radians(ubicacion1.longitud)
    lat2, lon2 = radians(ubicacion2.latitud), radians(ubicacion2.longitud)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000
    
    return c * r

def obtener_ruta_con_coordenadas(db: Session, desde_id: int, hacia_id: int):
    """
    Obtiene ruta con coordenadas y cálculos de distancia
    """
    ruta_ubicaciones = obtener_ruta(db, desde_id, hacia_id)
    
    if not ruta_ubicaciones:
        return None
    
    distancia_total = 0
    for i in range(len(ruta_ubicaciones) - 1):
        distancia_total += calcular_distancia_real(
            ruta_ubicaciones[i], 
            ruta_ubicaciones[i + 1]
        )
    
    return {
        "ubicaciones": ruta_ubicaciones,
        "distancia_total": distancia_total
    }
