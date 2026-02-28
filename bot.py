import os
import json
import logging
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

class CorrecaminosBot:
    def __init__(self, token=None):
        load_dotenv()
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.subscribers_file = "subscribers.json"
        self.subscribers = self._load_subscribers()

    def _load_subscribers(self):
        """Carga los chat_ids de usuarios que han hablado con el bot."""
        if os.path.exists(self.subscribers_file):
            try:
                with open(self.subscribers_file, "r") as f:
                    return set(json.load(f))
            except json.JSONDecodeError:
                return set()
        return set()

    def _save_subscribers(self):
        """Guarda la lista de usuarios en disco."""
        with open(self.subscribers_file, "w") as f:
            json.dump(list(self.subscribers), f)

    def fetch_new_users(self):
        """Lee los últimos mensajes del bot para suscribir a nuevos usuarios."""
        url = f"{self.base_url}/getUpdates"
        try:
            response = requests.get(url).json()
            if response.get("ok"):
                new_users = False
                for result in response.get("result", []):
                    if "message" in result:
                        chat_id = result["message"]["chat"]["id"]
                        if chat_id not in self.subscribers:
                            self.subscribers.add(chat_id)
                            new_users = True
                            username = result["message"]["chat"].get("username", "Unknown")
                            logging.info(f"Nuevo subscritor añadido: {username} ({chat_id})")
                
                if new_users:
                    self._save_subscribers()
        except Exception as e:
            logging.error(f"Error fetching updates: {e}")

    def broadcast(self, message: str):
        """Envía un mensaje a todos los usuarios suscritos."""
        if not self.subscribers:
            logging.warning("No hay suscriptores para enviar el broadcast.")
            return

        logging.info(f"Haciendo broadcast a {len(self.subscribers)} usuario(s)...")
        for chat_id in self.subscribers:
            self._send_message(chat_id, message)

    def _send_message(self, chat_id: int, text: str):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, json=payload).json()
            if not response.get("ok"):
                logging.error(f"Fallo enviando a {chat_id}: {response}")
        except Exception as e:
            logging.error(f"Excepción enviando a {chat_id}: {e}")

if __name__ == "__main__":
    from cercanias import Cercanias
    
    bot = CorrecaminosBot()
    # 1. Update subscriptors list listening to /start
    print("Buscando nuevos usuarios...")
    bot.fetch_new_users()
    
    if not bot.subscribers:
        print("No hay suscriptores. Abortando broadcast.")
        exit(0)
    
    # 2. Extract train schedule
    print("Extrayendo datos de la web de Adif...")
    try:
        c = Cercanias()
        trenes = c.obtener_proximos_trenes_madrid()
        
        if not trenes:
            mensaje = "⚠️ *Información Cercanías Majadahonda*\n\nNo se han encontrado trenes próximos con destino Madrid."
        else:
            mensaje = "🚆 *Próximos trenes destino Madrid (desde Majadahonda):*\n\n"
            # Limitar a los próximos 5
            for t in trenes[:5]:
                tiempo = f"{t['minutos_restantes']} min" if t['minutos_restantes'] > 0 else "Ahora"
                mensaje += f"• {t['hora_original']} - {tiempo} - {t['linea']}\n"
                
        bot.broadcast(mensaje)
        print("Broadcast completado exitosamente.")
    except Exception as e:
        error_msg = f"❌ Error extrayendo datos de Adif: {e}"
        print(error_msg)
        bot.broadcast(error_msg)
