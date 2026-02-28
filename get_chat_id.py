import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def get_chat_id():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    response = requests.get(url).json()
    
    if response.get("ok") and response.get("result"):
        # Coger el último mensaje
        latest = response["result"][-1]
        chat_id = latest["message"]["chat"]["id"]
        username = latest["message"]["chat"].get("username", "Unknown")
        text = latest["message"].get("text", "")
        print(f"Chat ID encontrado: {chat_id} (Usuario: {username}, Mensaje: '{text}')")
        return chat_id
    else:
        print("No se encontraron mensajes en el bot. Asegúrate de enviarle al menos uno (/start).")
        print(response)
        return None

if __name__ == "__main__":
    get_chat_id()
