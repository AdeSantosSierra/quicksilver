import os
import requests
import datetime
from dotenv import load_dotenv

class RutasGoogle:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.base_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        self.destino_default = "Metro Suanzes, Madrid"

    def obtener_tiempo_transito_neto(self, id_parada: str) -> str:
        """
        Calcula el tiempo neto desde que el cliente se monta en el transporte en `id_parada`
        hasta el destino (Metro Suanzes).
        """
        if not self.api_key or self.api_key == "AQUI_TU_API_KEY":
            return ""
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.legs.steps"
        }
        
        # Le decimos a Google explicitamente que es una parada de bus
        origen_query = f"Parada de autobus {id_parada}, Majadahonda, Madrid"
        if "estacion" in str(id_parada).lower():
            # Special handling if a literal string was passed for the train station
            origen_query = "Estación de Tren Cercanías Majadahonda, Madrid"
            
        body = {
            "origin": {
                "address": origen_query
            },
            "destination": {
                "address": self.destino_default
            },
            "travelMode": "TRANSIT",
            "transitPreferences": {
                "allowedTravelModes": ["BUS", "SUBWAY", "TRAIN"]
            },
            "languageCode": "es-ES"
        }
        
        try:
            res = requests.post(self.base_url, headers=headers, json=body, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            if not data or not data.get("routes"):
                return ""
            
            steps = data["routes"][0].get("legs", [{}])[0].get("steps", [])
            
            first_departure = None
            last_arrival = None
            walk_seconds_after = 0
            
            for step in steps:
                mode = step.get("travelMode")
                transit_details = step.get("transitDetails", {})
                stop_details = transit_details.get("stopDetails", {})
                
                dep_time_str = stop_details.get("departureTime") or transit_details.get("departureTime")
                arr_time_str = stop_details.get("arrivalTime") or transit_details.get("arrivalTime")

                if mode == "TRANSIT":
                    if first_departure is None and dep_time_str:
                        first_departure = dep_time_str
                    if arr_time_str:
                        last_arrival = arr_time_str
                    walk_seconds_after = 0
                elif mode == "WALK":
                    if first_departure is not None:
                        d_str = step.get("duration") or step.get("staticDuration", "0s")
                        if d_str.endswith("s"):
                            walk_seconds_after += int(d_str[:-1])
            
            if first_departure and last_arrival:
                fmt = "%Y-%m-%dT%H:%M:%SZ"
                t1 = datetime.datetime.strptime(first_departure, fmt)
                t2 = datetime.datetime.strptime(last_arrival, fmt)
                
                diff_seconds = (t2 - t1).total_seconds()
                total_travel_seconds = diff_seconds + walk_seconds_after
                
                minutos = int(total_travel_seconds / 60)
                return f"{minutos} min"
                
            return ""
                
        except Exception as e:
            print(f"Error google API en {id_parada}: {e}")
            return ""

if __name__ == "__main__":
    rg = RutasGoogle()
    t = rg.obtener_tiempo_transito_neto("12910")
    print(f"Tiempo neto desde Parada 12910 a Suanzes: {t}")
    t_tren = rg.obtener_tiempo_transito_neto("estacion")
    print(f"Tiempo neto desde Cercanías a Suanzes: {t_tren}")
