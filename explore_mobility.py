import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
client_id = os.getenv("MOBILITYLABS_CLIENT_ID")
passkey = os.getenv("MOBILITYLABS_PASSKEY")

def run():
    print("Testing MobilityLabs Authentication...")
    headers = {
        "X-ClientId": client_id,
        "passKey": passkey,
        "idClient": client_id
    }
    
    for version in ["v1", "v2", "v3"]:
        login_url = f"https://openapi.emtmadrid.es/{version}/mobilitylabs/user/login/"
        for method in ["GET", "POST"]:
            try:
                if method == "GET":
                    res = requests.get(login_url, headers=headers)
                else:
                    res = requests.post(login_url, headers=headers)
                
                print(f"[{version}] {method} Status: {res.status_code}")
                if res.status_code == 200:
                    print(f"[{version}] {method} Body: {res.text[:300]}")
                else:
                    print(f"[{version}] {method} Error: {res.text}")
            except Exception as e:
                print(f"Error {version} {method}: {e}")
            
if __name__ == "__main__":
    run()
