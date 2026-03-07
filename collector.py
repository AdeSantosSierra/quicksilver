import os
import time
import datetime
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

from cercanias import Cercanias
from buses import Buses

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

def get_mongo_collection():
    if not MONGO_URI:
        logging.error("No se encontró MONGO_URI en el entorno.")
        return None
    try:
        client = MongoClient(MONGO_URI)
        # Usamos directamente 'transporte_db' sin pedir la default db
        db = client['transporte_db']
        collection = db['extracciones']
        return collection
    except Exception as e:
        logging.error(f"Error conectando a MongoDB: {e}")
        return None

def normalize_bus_id(cod_parada: str) -> str:
    # 8 caracteres, rellenando con 0 a la izquierda
    cod_parada = str(cod_parada).replace("8_", "")
    return cod_parada.zfill(8)

from playwright.sync_api import sync_playwright

def collect_data(page):
    collection = get_mongo_collection()
    if collection is None:
        return

    ahora = datetime.datetime.now()
    documentos = []

    # 1. Autobuses
    buses = Buses()
    paradas_buses = ["17699", "07305", "11980", "02419", "17480", "09478"]
    
    for cod_parada in paradas_buses:
        logging.info(f"Extrayendo bus {cod_parada}...")
        try:
            tiempos = buses.obtener_tiempos_parada(cod_parada)
            for t in tiempos:
                documentos.append({
                    "timestamp": ahora,
                    "parada": normalize_bus_id(cod_parada),
                    "linea": str(t['linea']),
                    "destino": str(t.get('destino', '')),
                    "hora_llegada": str(t['hora_llegada']),
                    "minutos_restantes": t['minutos_restantes'],
                    "medio_transporte": "Bus"
                })
        except Exception as e:
            logging.error(f"Error en bus {cod_parada}: {e}")

    # 2. Cercanías
    # Majadahonda
    c_majadahonda = Cercanias(url="https://www.adif.es/w/10007-majadahonda", page=page)
    logging.info("Extrayendo Cercanías Majadahonda...")
    try:
        trenes_m = c_majadahonda.obtener_proximos_trenes_madrid()
        for t in trenes_m:
            documentos.append({
                "timestamp": ahora,
                "parada": "Majadaho",
                "linea": str(t['linea']),
                "destino": str(t.get('destino', '')),
                "hora_llegada": str(t['hora_original']),
                "minutos_restantes": t['minutos_restantes'],
                "anden": str(t.get('anden', '')),
                "medio_transporte": "Cercanias"
            })
    except Exception as e:
        logging.error(f"Error en Cercanías Majadahonda: {e}")

    # Aravaca
    c_aravaca = Cercanias(url="https://www.adif.es/-/10001-aravaca", page=page)
    logging.info("Extrayendo Cercanías Aravaca...")
    try:
        trenes_a = c_aravaca.obtener_proximos_trenes_madrid()
        for t in trenes_a:
            documentos.append({
                "timestamp": ahora,
                "parada": "Aravaca0",
                "linea": str(t['linea']),
                "destino": str(t.get('destino', '')),
                "hora_llegada": str(t['hora_original']),
                "minutos_restantes": t['minutos_restantes'],
                "anden": str(t.get('anden', '')),
                "medio_transporte": "Cercanias"
            })
    except Exception as e:
        logging.error(f"Error en Cercanías Aravaca: {e}")

    # Insertar en base de datos
    if documentos:
        try:
            collection.insert_many(documentos)
            logging.info(f"¡{len(documentos)} documentos insertados correctamente en MongoDB!")
        except Exception as e:
            logging.error(f"Error insertando en Mongo: {e}")
            
        # Opcional: Limpiar datos más antiguos de 2 horas para no inflar la BB.DD.
        try:
            limite_borrado = ahora - datetime.timedelta(hours=2)
            res = collection.delete_many({"timestamp": {"$lt": limite_borrado}})
            if res.deleted_count > 0:
                logging.info(f"Limpiados {res.deleted_count} documentos antiguos.")
        except Exception as e:
            logging.error(f"Error limpiando Mongo: {e}")
    else:
        logging.info("No se han extraído datos nuevos en este ciclo.")

def main():
    logging.info("Iniciando Collector daemon...")
    with sync_playwright() as p:
        logging.info("Iniciando engine de Playwright Firefox...")
        browser = p.firefox.launch(headless=True)
        
        while True:
            logging.info("Iniciando ciclo de extracción...")
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            try:
                collect_data(page)
            except Exception as e:
                logging.error(f"Error grave crítico en collect_data: {e}")
            finally:
                page.close()
                context.close()
                
            logging.info("Ciclo terminado. Durmiendo 60 segundos...")
            time.sleep(60)

if __name__ == "__main__":
    main()
