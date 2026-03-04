import os
import json
import logging
import requests
import datetime
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

    def _send_image(self, chat_id: int, image_path: str, caption: str = ""):
        url = f"{self.base_url}/sendPhoto"
        try:
            with open(image_path, "rb") as photo:
                payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
                files = {"photo": photo}
                response = requests.post(url, data=payload, files=files).json()
                if not response.get("ok"):
                    logging.error(f"Fallo enviando foto a {chat_id}: {response}")
        except Exception as e:
            logging.error(f"Excepción enviando foto a {chat_id}: {e}")

    def broadcast_image(self, image_path: str, caption: str = ""):
        """Envía una imagen a todos los usuarios suscritos."""
        if not self.subscribers:
            logging.warning("No hay suscriptores para enviar el broadcast de imagen.")
            return

        logging.info(f"Haciendo broadcast de imagen a {len(self.subscribers)} usuario(s)...")
        for chat_id in self.subscribers:
            self._send_image(chat_id, image_path, caption)

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
    import dgt_cameras
    
    bot = CorrecaminosBot()
    print("Buscando nuevos usuarios...")
    bot.fetch_new_users()
    
    if not bot.subscribers:
        print("No hay suscriptores. Abortando broadcast.")
        exit(0)
    
    print("Extrayendo datos de la web de Adif y CRTM...")
    bloque_transportes = ""
    ahora = datetime.datetime.now()
    
    # 1. Trenes de Cercanías
    try:
        c = Cercanias()
        trenes = c.obtener_proximos_trenes_madrid()
        
        bloque_transportes += f"🚆 *Cercanías*\n"
        if not trenes:
            bloque_transportes += "No hay trenes próximos hacia Madrid.\n\n"
        else:
            for t in trenes[:5]:
                linea_tren = t['linea']
                if t['minutos_restantes'] >= 0:
                    llegada_dt = ahora + datetime.timedelta(minutes=t['minutos_restantes'])
                    llegada_str = llegada_dt.strftime('%H:%M')
                else:
                    llegada_str = t['hora_original']
                bloque_transportes += f"• {llegada_str} - {linea_tren}\n"
            bloque_transportes += "\n"
    except Exception as e:
        bloque_transportes += f"❌ Error extrayendo Cercanías: {e}\n\n"

    # 2. Autobuses Interurbanos
    try:
        b = Buses()
        paradas_config = [
            {"id": "17699", "nombre": "Farmacia Rotonda FGL", "limite": 3},
            {"id": "07305", "nombre": "Estación sentido Madrid", "limite": 3}
        ]
        
        for parada in paradas_config:
            id_parada = parada["id"]
            nombre = f"{parada['nombre']} ({id_parada})"
            limite = parada["limite"]
            
            tiempos_buses = b.obtener_tiempos_parada(id_parada)
            bloque_transportes += f"🚌 *{nombre}*\n"
                
            if not tiempos_buses:
                bloque_transportes += "No hay buses próximos.\n\n"
            else:
                for t in tiempos_buses[:limite]:
                    bloque_transportes += f"• {t['hora_llegada']} - {t['linea']}\n"
                bloque_transportes += "\n"
    except Exception as e:
        bloque_transportes += f"❌ Error extrayendo Autobuses: {e}"
        
    print("Enviando estado de transporte...")
    bot.broadcast(bloque_transportes.strip())
    
    # 3. DGT Cameras
    print("Extrayendo cámaras de la DGT...")
    urls = dgt_cameras.get_dgt_cams()
    if urls:
        print(f"Encontradas {len(urls)} cámaras. Creando collage...")
        collage_path = "dgt_collage.jpg"
        if dgt_cameras.create_collage(urls, output_path=collage_path):
            print("Collage creado. Enviando a Telegram...")
            bot.broadcast_image(collage_path, caption="📷 *Cámaras DGT (A-6)*")
        else:
            print("No se pudo crear el collage.")
    else:
        print("No se encontraron URLs de cámaras DGT.")

    print("Proceso completado.")
