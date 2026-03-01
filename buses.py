import requests
import time
from datetime import datetime
from typing import List, Dict, Union

class Buses:
    def __init__(self):
        self.base_url = "https://www.crtm.es/widgets/api"

    def _calcular_tiempo_restante(self, time_iso: str) -> int:
        """
        Calcula los minutos restantes recibiendo un string ISO 8601 con zona horaria.
        Ejemplo: "2026-02-28T01:36:37+01:00"
        """
        try:
            # Parseamos la fecha directamente (Python 3.7+ soporta fromisoformat pero puede fallar con algunas Z)
            # En caso de fallar, extraemos la fecha local recortando el offset
            if "+" in time_iso:
                time_iso_clean = time_iso.split("+")[0]
            elif "-" in time_iso[11:]:
                # Maneja casuísticas raras de offset negativo, cortamos por el último guion
                parts = time_iso.rsplit("-", 1)
                time_iso_clean = parts[0]
            else:
                time_iso_clean = time_iso.replace("Z", "")
                
            hora_llegada = datetime.fromisoformat(time_iso_clean)
            ahora = datetime.now()
            
            diferencia_mins = int((hora_llegada - ahora).total_seconds() / 60)
            
            # Si el bus ya ha pasado (tiempos negativos), asumimos que es "ahora" si está en margen de 1 min.
            if diferencia_mins < 0:
                if diferencia_mins > -2:
                    return 0
                return -1
            return diferencia_mins
        except Exception as e:
            print(f"Error parseando fecha '{time_iso}': {e}")
            return -1

    def obtener_tiempos_parada(self, cod_parada: str) -> List[Dict[str, Union[str, int]]]:
        """
        Devuelve los próximos autobuses para una parada.
        El código de parada interurbana debe ser en formato '8_01234' o usar '01234'.
        Si se le pasa un int o string numérico, se prefija con '8_' por defecto (interurbanos).
        """
        # Formatear el stop ID al estilo de la API (ej: 8_06114 -> código 8 = Interurbano)
        if "_" not in str(cod_parada):
            cod_parada = f"8_{cod_parada}"
            
        url = f"{self.base_url}/GetStopsTimes.php?codStop={cod_parada}&type=0&orderBy=2&stopTimesByIti="
        resultados = []
        
        data = {}
        for intento in range(4):
            try:
                res = requests.get(url, timeout=10)
                res.raise_for_status()
                data = res.json()
                break
            except requests.exceptions.Timeout:
                # Si agota el intento 3 (cuarto intento), se rinde
                if intento == 3:
                    print(f"Timeout CRTM API para la parada {cod_parada} tras 4 intentos.")
                    return resultados
                time.sleep(2)
            except Exception as e:
                print(f"Error obteniendo tiempos de parada {cod_parada}: {e}")
                return resultados
                
        tiempos_list = data.get("stopTimes", {}).get("times", {}).get("Time", [])
        
        # En caso de venir vacío o no ser lista
        if not tiempos_list:
            return resultados
            
        if not isinstance(tiempos_list, list):
            tiempos_list = [tiempos_list]
            
        for t in tiempos_list:
            linea_info = t.get("line", {})
            nombre_linea = linea_info.get("shortDescription", "Desconocida")
            destino = t.get("destination", "Destino Desconocido")
            
            # 'time' trae la hora estimada de llegada
            time_iso = t.get("time")
            min_restantes = self._calcular_tiempo_restante(time_iso)
            
            if min_restantes >= 0:
                resultados.append({
                    "linea": nombre_linea,
                    "destino": destino,
                    "minutos_restantes": min_restantes,
                    "hora_llegada": time_iso.split("T")[1][:5] if time_iso and "T" in time_iso else "??"
                })
                
        # API can return unsorted by time sometimes, ensure sorted:
        resultados.sort(key=lambda x: x["minutos_restantes"])
        return resultados

if __name__ == "__main__":
    buses = Buses()
    # Parada 06114 de ejemplo: Ctra. Boadilla - Urb. Roza Martín (Majadahonda)
    print("Probando con parada 06114 (Interurbanos Majadahonda)...")
    tiempos = buses.obtener_tiempos_parada("06114")
    for t in tiempos:
        print(f"Línea {t['linea']} hacia {t['destino']} -> {t['minutos_restantes']} min ({t['hora_llegada']})")
