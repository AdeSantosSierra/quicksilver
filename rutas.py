import os
import requests
from dotenv import load_dotenv

class RutasGoogle:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.base_url = "https://maps.googleapis.com/maps/api/directions/json"
        self.destino_default = "Intercambiador de Moncloa, Madrid"

    def obtener_tiempo_a_moncloa(self, origen: str) -> str:
        """
        Calcula el tiempo estimado en bus desde el origen hasta Moncloa.
        Devuelve un string con texto (ej: "22 min") o un string vacío si hay error.
        """
        if not self.api_key or self.api_key == "AQUI_TU_API_KEY":
            return "" # Graceful exit if API key is not configured
        
        params = {
            "origin": f"{origen}, Majadahonda",
            "destination": self.destino_default,
            "mode": "transit",
            "transit_mode": "bus",
            "departure_time": "now",
            "key": self.api_key,
            "language": "es"
        }
        
        try:
            res = requests.get(self.base_url, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            if data.get("status") == "OK" and data.get("routes"):
                # Obtenemos el leg principal (solo hay 1 leg para origen->destino simple)
                leg = data["routes"][0]["legs"][0]
                
                # Para transporte publico al usar departure_time=now, duration es bastante precisa
                # También podríamos tener 'duration_in_traffic' pero para transit a veces solo devuelve 'duration'
                duracion = leg.get("duration", {}).get("text", "")
                return duracion
            else:
                print(f"Aviso Google API: {data.get('status')} - {data.get('error_message', '')}")
                return ""
        except Exception as e:
            print(f"Error consultando ruta a Google Maps desde {origen}: {e}")
            return ""

if __name__ == "__main__":
    rg = RutasGoogle()
    if not rg.api_key:
        print("Falta GOOGLE_MAPS_API_KEY en .env")
    else:
        tiempo = rg.obtener_tiempo_a_moncloa("Colegio FGL")
        print(f"Tiempo a Moncloa desde Colegio FGL: {tiempo}")
