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

    def obtener_tiempo_transito_neto(self, id_parada: str) -> dict:
        """
        Calcula el tiempo neto desde que el cliente se monta en el transporte en `id_parada`
        hasta el destino (Metro Suanzes).
        Devuelve un diccionario con el tiempo y la ruta a seguir.
        """
        if not self.api_key or self.api_key == "AQUI_TU_API_KEY":
            return {"tiempo": "", "ruta": ""}
        
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
            "computeAlternativeRoutes": True,
            "languageCode": "es-ES"
        }
        
        try:
            res = requests.post(self.base_url, headers=headers, json=body, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            routes = data.get("routes", [])
            if not routes:
                return {"tiempo": "", "ruta": ""}
            
            # Function to parse a single route object into our dict format
            def parse_route(r):
                steps = r.get("legs", [{}])[0].get("steps", [])
                
                first_departure = None
                last_arrival = None
                walk_seconds_after = 0
                
                ruta_steps = []
                detalles_pasos = []
                en_ruta = False
                first_transit_line = None
                
                for step in steps:
                    mode = step.get("travelMode")
                    transit_details = step.get("transitDetails", {})
                    stop_details = transit_details.get("stopDetails", {})
                    
                    dep_time_str = stop_details.get("departureTime") or transit_details.get("departureTime")
                    arr_time_str = stop_details.get("arrivalTime") or transit_details.get("arrivalTime")

                    step_dur_str = step.get("duration") or step.get("staticDuration", "0s")
                    step_min = int(int(step_dur_str[:-1]) / 60) if step_dur_str.endswith("s") else 0

                    if mode == "TRANSIT":
                        en_ruta = True
                        if first_departure is None and dep_time_str:
                            first_departure = dep_time_str
                        if arr_time_str:
                            last_arrival = arr_time_str
                        walk_seconds_after = 0
                        
                        # Store route lines
                        line = transit_details.get("transitLine", {})
                        short_name = line.get("nameShort", "")
                        name = line.get("name", "")
                        veh_type = line.get("vehicle", {}).get("type", "")
                        
                        if short_name:
                            if veh_type == "SUBWAY" and short_name.isdigit():
                                linea_act = f"L{short_name}"
                            else:
                                linea_act = short_name
                        else:
                            linea_act = name.split('-')[0].strip()
                            
                        if first_transit_line is None:
                            first_transit_line = linea_act
                            
                        ruta_steps.append(linea_act)
                        
                        stop_arr = stop_details.get("arrivalStop", {}).get("name", "Destino")
                        stop_dep = stop_details.get("departureStop", {}).get("name", "Origen")
                        
                        detalles_pasos.append({
                            "modo": "TRANSIT",
                            "linea": linea_act,
                            "origen": stop_dep,
                            "destino": stop_arr,
                            "duracion": step_min
                        })
                            
                    elif mode == "WALK":
                        if en_ruta:
                            if d_str := step.get("duration") or step.get("staticDuration", "0s"):
                                if d_str.endswith("s"):
                                    walk_seconds_after += int(d_str[:-1])
                            detalles_pasos.append({
                                "modo": "WALK",
                                "duracion": step_min,
                                "instruccion": "Transbordo / Andar"
                            })
                
                if first_departure and last_arrival:
                    fmt = "%Y-%m-%dT%H:%M:%SZ"
                    t1 = datetime.datetime.strptime(first_departure, fmt)
                    t2 = datetime.datetime.strptime(last_arrival, fmt)
                    
                    diff_seconds = (t2 - t1).total_seconds()
                    total_travel_seconds = diff_seconds + walk_seconds_after
                    minutos = int(total_travel_seconds / 60)
                    ruta_str = " ➔ ".join(ruta_steps)
                    return {"tiempo": f"{minutos} min", "ruta": ruta_str, "detalles": detalles_pasos, "linea_principal": first_transit_line}
                    
                return None

            # Parse all alternative routes
            parsed_routes = []
            for r in routes:
                pr = parse_route(r)
                if pr:
                    parsed_routes.append(pr)
            
            if not parsed_routes:
                return {"tiempo": "", "ruta": ""}
                
            # If train station, return a dict mapping line names (e.g. "C10", "C7") to their best route
            if "estacion" in str(id_parada).lower():
                mapa_lineas = {}
                for pr in parsed_routes:
                    lin = pr["linea_principal"]
                    if lin:
                        # Only save the fastest one if there are duplicates for same line
                        if lin not in mapa_lineas or int(pr["tiempo"].split()[0]) < int(mapa_lineas[lin]["tiempo"].split()[0]):
                            mapa_lineas[lin] = pr
                # Fallback to returning just the fastest overall if parsing failed
                if not mapa_lineas:
                    return parsed_routes[0]
                return mapa_lineas
            
            # If it's a bus stop, just return the fastest overall route
            parsed_routes.sort(key=lambda x: int(x["tiempo"].split()[0]))
            return parsed_routes[0]
            
                
        except Exception as e:
            print(f"Error google API en {id_parada}: {e}")
            return {"tiempo": "", "ruta": ""}

if __name__ == "__main__":
    rg = RutasGoogle()
    t = rg.obtener_tiempo_transito_neto("12910")
    print(f"Tiempo neto desde Parada 12910 a Suanzes: {t}")
    t_tren = rg.obtener_tiempo_transito_neto("estacion")
    print(f"Tiempo neto desde Cercanías a Suanzes: {t_tren}")
