import requests
import json

BASE_URL = "https://www.crtm.es/widgets/api"

def run():
    print("Testing CRTM raw API for bus locations using GetLineLocation...")
    try:
        # Stop: 11463 (Ctra. Pozuelo), Line: 8__651___ (Interurban), type/mode 8
        url = f"{BASE_URL}/GetLineLocation.php?mode=8&codItinerary=&codLine=8__651___&codStop=8_11463&direction=1"
        res = requests.get(url)
        data = res.json()
        print(json.dumps(data, indent=2))
        
        url2 = f"{BASE_URL}/GetLineLocation.php?mode=8&codItinerary=&codLine=8__651___&codStop=8_11463&direction=2"
        res2 = requests.get(url2)
        print("Direction 2:")
        print(json.dumps(res2.json(), indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
        
if __name__ == "__main__":
    run()
