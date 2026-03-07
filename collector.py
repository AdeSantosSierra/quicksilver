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

    # 1. Autobuses e Intercambiadores (Metro)
    buses_api = Buses()
    # 4_53 (Moncloa - L3/L6), 4_9 (Bilbao - L1/L4), 4_1 (Tribunal - L1/L10), 4_96 (Casa Campo - L5/L10)
    paradas_buses = ["17699", "07305", "11980", "02419", "17480", "09478", "4_53", "4_9", "4_1", "4_96"]
    
    for cod_parada in paradas_buses:
        logging.info(f"Extrayendo datos de {cod_parada}...")
        try:
            raw_data = buses_api.obtener_datos_crudos_parada(cod_parada)
            stop_times = raw_data.get("stopTimes", {})
            times_list = stop_times.get("times", {}).get("Time", [])
            if not isinstance(times_list, list): times_list = [times_list]
            
            seen_lines_in_times = set()
            
            # --- Fase 6: Cálculo de Intervalos Medios (Frecuencias) ---
            # Agrupamos por línea para calcular el gap medio entre trenes
            line_intervals = {} # { "L3": [min1, min2, ...], "L6": [...] }
            
            # Pre-procesar tiempos para frecuencias
            for t in times_list:
                if not t: continue
                linea_obj = t.get("line", {})
                l_name = str(linea_obj.get("shortDescription", "?"))
                time_iso = t.get("time")
                mins = buses_api._calcular_tiempo_restante(time_iso)
                if mins >= 0:
                    if l_name not in line_intervals: line_intervals[l_name] = []
                    line_intervals[l_name].append(mins)
            
            frecuencias = {} # { "L3": 6.5, ... }
            for l_name, mins_list in line_intervals.items():
                if len(mins_list) > 1:
                    mins_sorted = sorted(mins_list)
                    gaps = [mins_sorted[i+1] - mins_sorted[i] for i in range(len(mins_sorted)-1)]
                    # Filtramos gaps de 0 o 1 min que suelen ser el mismo tren en dos andenes o error de API
                    gaps = [g for g in gaps if g > 1]
                    if gaps:
                        frecuencias[l_name] = round(sum(gaps) / len(gaps), 1)

            # Procesar tiempos reales e insertar en documentos
            for t in times_list:
                if not t: continue
                linea_obj = t.get("line", {})
                nombre_linea = str(linea_obj.get("shortDescription", "?"))
                time_iso = t.get("time")
                minutos = buses_api._calcular_tiempo_restante(time_iso)
                
                if minutos >= 0:
                    seen_lines_in_times.add(nombre_linea)
                    doc = {
                        "timestamp": ahora,
                        "parada": normalize_bus_id(cod_parada) if "_" not in cod_parada else cod_parada,
                        "linea": nombre_linea,
                        "destino": str(t.get('destino', '')),
                        "hora_llegada": time_iso.split("T")[1][:5] if time_iso and "T" in time_iso else "??",
                        "minutos_restantes": minutos,
                        "medio_transporte": "Metro" if cod_parada.startswith("4_") else "Bus"
                    }
                    if nombre_linea in frecuencias:
                        doc["frecuencia_media"] = frecuencias[nombre_linea]
                    documentos.append(doc)

            # Detección de cortes (Phase 5):
            # Si una línea está en linesStatus pero no tiene ningún tiempo asociado en 'times',
            # guardamos un aviso de -999.
            line_status_list = stop_times.get("linesStatus", {}).get("LineStatus", [])
            if not isinstance(line_status_list, list): line_status_list = [line_status_list]
            
            for ls in line_status_list:
                l_info = ls.get("line", {})
                l_name = str(l_info.get("shortDescription", ""))
                if l_name and l_name != "" and l_name not in seen_lines_in_times:
                    logging.warning(f"Posible corte en línea {l_name} (parada {cod_parada})")
                    documentos.append({
                        "timestamp": ahora,
                        "parada": normalize_bus_id(cod_parada) if "_" not in cod_parada else cod_parada,
                        "linea": l_name,
                        "destino": "SIN SERVICIO / CORTE",
                        "hora_llegada": "--:--",
                        "minutos_restantes": -999,
                        "medio_transporte": "Metro" if cod_parada.startswith("4_") else "Bus"
                    })

        except Exception as e:
            logging.error(f"Error en parada {cod_parada}: {e}")

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
