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
    from buses import Buses
    from rutas import RutasGoogle
    
    bot = CorrecaminosBot()
    print("Buscando nuevos usuarios...")
    bot.fetch_new_users()
    
    if not bot.subscribers:
        print("No hay suscriptores. Abortando broadcast.")
        exit(0)
    
    print("Extrayendo datos de la web de Adif y CRTM...")
    mensaje_final = ""
    
    # 1. Trenes de Cercanías
    try:
        c = Cercanias()
        trenes = c.obtener_proximos_trenes_madrid()
        
        if not trenes:
            mensaje_final += "⚠️ *Cercanías Majadahonda*\nNo hay trenes próximos hacia Madrid.\n\n"
        else:
            mensaje_final += "🚆 *Cercanías destino Madrid:*\n"
            for t in trenes[:5]:
                tiempo = f"{t['minutos_restantes']} min" if t['minutos_restantes'] > 0 else "Ahora"
                mensaje_final += f"• {t['hora_original']} - {tiempo} - {t['linea']}\n"
            mensaje_final += "\n"
    except Exception as e:
        mensaje_final += f"❌ Error extrayendo Cercanías: {e}\n\n"

    # 2. Autobuses Interurbanos
    try:
        b = Buses()
        rg = RutasGoogle()
        
        paradas_config = [
            {"id": "12910", "nombre": "Colegio FGL", "limite": 3},
            {"id": "17699", "nombre": "Farmacia Rotonda FGL", "limite": 5},
            {"id": "07305", "nombre": "Estación sentido Madrid", "limite": 7}
        ]
        
        for parada in paradas_config:
            id_parada = parada["id"]
            nombre = parada["nombre"]
            limite = parada["limite"]
            
            tiempos_buses = b.obtener_tiempos_parada(id_parada)
            
            # Extraer tiempo estimado desde este origen a Moncloa usando Google
            tiempo_viaje = rg.obtener_tiempo_a_moncloa(nombre)
            texto_viaje = f"(~{tiempo_viaje} a Moncloa)" if tiempo_viaje else ""
            
            mensaje_final += f"🚌 *Buses - {nombre} {texto_viaje}:*\n"
            if not tiempos_buses:
                mensaje_final += "No hay buses próximos.\n\n"
            else:
                for t in tiempos_buses[:limite]:
                    tiempo = f"{t['minutos_restantes']} min" if t['minutos_restantes'] > 0 else "Ahora"
                    mensaje_final += f"• {t['hora_llegada']} - {tiempo} - {t['linea']}\n"
                mensaje_final += "\n"
    except Exception as e:
        mensaje_final += f"❌ Error extrayendo Autobuses: {e}"
        
    bot.broadcast(mensaje_final.strip())
    print("Broadcast completado exitosamente.")
