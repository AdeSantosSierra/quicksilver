import os
import requests
import json
from dotenv import load_dotenv

def test_metro_route():
    load_dotenv()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Falta GOOGLE_MAPS_API_KEY en .env")
        return

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    
    # We want route from Majadahonda all the way to Suanzes (Metro L5)
    # The API will figure out the legs: Bus to Moncloa -> Metro L3 -> Metro L5
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.legs.steps"
    }

    body = {
        "origin": {
            "address": "Colegio FGL, Majadahonda"
        },
        "destination": {
            "address": "Metro Suanzes, Madrid"
        },
        "travelMode": "TRANSIT",
        "transitPreferences": {
            "allowedTravelModes": ["BUS", "SUBWAY"]
        },
        "languageCode": "es-ES"
    }

    print("Consultando ruta completa a Suanzes (Bus + Metro)...\n")
    try:
        res = requests.post(url, headers=headers, json=body, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        if not data.get("routes"):
            print("No se encontraron rutas.")
            return

        ru = data["routes"][0]
        total_duration = ru.get("duration", "")
        print(f"Duración TOTAL del viaje: {total_duration}")
        print("-" * 40)
        
        # Parse the steps inside the single leg
        leg = ru["legs"][0]
        steps = leg.get("steps", [])
        import datetime
        
        first_departure = None
        last_arrival = None
        walk_seconds_after = 0
        
        for step in steps:
            mode = step.get("travelMode")
            # Extraer transitDetails robustamente
            transit_details = step.get("transitDetails", {})
            stop_details = transit_details.get("stopDetails", {})
            # fallback si stopDetails no viene, aunque la documentacion dice que si
            # a veces viene directo en transitDetails
            dep_time_str = stop_details.get("departureTime") or transit_details.get("departureTime")
            arr_time_str = stop_details.get("arrivalTime") or transit_details.get("arrivalTime")

            if mode == "TRANSIT":
                if first_departure is None and dep_time_str:
                    first_departure = dep_time_str
                if arr_time_str:
                    last_arrival = arr_time_str
                walk_seconds_after = 0 # reset walk time because a new transit leg appeared
            elif mode == "WALK":
                if first_departure is not None:
                    # Only count walks AFTER the first transit
                    d_str = step.get("duration") or step.get("staticDuration", "0s")
                    if d_str.endswith("s"):
                        walk_seconds_after += int(d_str[:-1])
                        
        print(f"First Departure: {first_departure}")
        print(f"Last Arrival: {last_arrival}")
        print(f"Walk Seconds After: {walk_seconds_after}")
        
        if first_departure and last_arrival:
            # format: 2026-03-01T01:59:02Z
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            t1 = datetime.datetime.strptime(first_departure, fmt)
            t2 = datetime.datetime.strptime(last_arrival, fmt)
            
            diff_seconds = (t2 - t1).total_seconds()
            total_travel_seconds = diff_seconds + walk_seconds_after
            
            print(f"Total time ON MODE: {int(diff_seconds)}s")
            print(f"Total precise travel time: {int(total_travel_seconds / 60)} minutos")
        else:
            print("No se pudieron extraer tiempos exactos.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_metro_route()
