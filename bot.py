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
    bloque_transportes = ""
    todas_opciones = []
    
    rg = RutasGoogle()
    ahora = datetime.datetime.now()
    
    def extraer_minutos(texto):
        if texto and "min" in texto:
            try:
                return int(texto.split()[0])
            except ValueError:
                return 0
        return 0
    
    # 1. Trenes de Cercanías
    try:
        c = Cercanias()
        trenes = c.obtener_proximos_trenes_madrid()
        
        tiempo_tren_suanzes_dict = rg.obtener_tiempo_transito_neto("estacion")
        tiempo_tren_suanzes = tiempo_tren_suanzes_dict.get("tiempo", "")
        ruta_tren_suanzes = tiempo_tren_suanzes_dict.get("ruta", "")
        detalles_tren = tiempo_tren_suanzes_dict.get("detalles", [])
        minutos_tren_suanzes = extraer_minutos(tiempo_tren_suanzes)
        texto_viaje_tren = f"(~{tiempo_tren_suanzes} a Suanzes | 🗺️ {ruta_tren_suanzes})" if tiempo_tren_suanzes else ""
        
        if not trenes:
            bloque_transportes += "⚠️ *Cercanías Majadahonda*\nNo hay trenes próximos hacia Madrid.\n\n"
        else:
            bloque_transportes += f"🚆 *Cercanías destino Madrid {texto_viaje_tren}:*\n"
            for t in trenes[:3]:
                tiempo = f"{t['minutos_restantes']} min" if t['minutos_restantes'] > 0 else "Ahora"
                
                texto_llegada_suanzes = ""
                if minutos_tren_suanzes > 0 and t['minutos_restantes'] >= 0:
                    llegada_dt = ahora + datetime.timedelta(minutes=t['minutos_restantes'] + minutos_tren_suanzes)
                    texto_llegada_suanzes = f" 🏁 Llega a las {llegada_dt.strftime('%H:%M')}"
                    
                    todas_opciones.append({
                        "tipo": "🚆 Cercanías",
                        "llegada": llegada_dt,
                        "tiempo_salida_str": tiempo,
                        "min_restantes": t['minutos_restantes'],
                        "linea": t['linea'],
                        "tiempo_trayecto": tiempo_tren_suanzes,
                        "detalles": detalles_tren,
                        "hora_original": t['hora_original']
                    })
                    
                bloque_transportes += f"• {t['hora_original']} - {tiempo} - {t['linea']}{texto_llegada_suanzes}\n"
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
            nombre = parada["nombre"]
            limite = parada["limite"]
            
            tiempos_buses = b.obtener_tiempos_parada(id_parada)
            
            # Extraer tiempo neto de viaje (sin el transbordo inicial), usando su ID de parada
            tiempo_viaje_bus_dict = rg.obtener_tiempo_transito_neto(id_parada)
            tiempo_viaje_bus = tiempo_viaje_bus_dict.get("tiempo", "")
            ruta_viaje_bus = tiempo_viaje_bus_dict.get("ruta", "")
            detalles_bus = tiempo_viaje_bus_dict.get("detalles", [])
            minutos_viaje_bus = extraer_minutos(tiempo_viaje_bus)
            texto_viaje_bus = f"(~{tiempo_viaje_bus} a Suanzes | 🗺️ {ruta_viaje_bus})" if tiempo_viaje_bus else ""
            
            bloque_transportes += f"🚌 *Buses - {nombre} {texto_viaje_bus}:*\n"
            if not tiempos_buses:
                bloque_transportes += "No hay buses próximos.\n\n"
            else:
                for t in tiempos_buses[:limite]:
                    tiempo = f"{t['minutos_restantes']} min" if t['minutos_restantes'] > 0 else "Ahora"
                    
                    texto_llegada_suanzes = ""
                    if minutos_viaje_bus > 0 and t['minutos_restantes'] >= 0:
                        llegada_dt = ahora + datetime.timedelta(minutes=t['minutos_restantes'] + minutos_viaje_bus)
                        texto_llegada_suanzes = f" 🏁 Llega a las {llegada_dt.strftime('%H:%M')}"
                        
                        todas_opciones.append({
                            "tipo": f"🚌 {nombre}",
                            "llegada": llegada_dt,
                            "tiempo_salida_str": tiempo,
                            "min_restantes": t['minutos_restantes'],
                            "linea": t['linea'],
                            "tiempo_trayecto": tiempo_viaje_bus,
                            "detalles": detalles_bus,
                            "hora_original": t['hora_llegada']
                        })
                        
                    bloque_transportes += f"• {t['hora_llegada']} - {tiempo} - {t['linea']}{texto_llegada_suanzes}\n"
                bloque_transportes += "\n"
    except Exception as e:
        bloque_transportes += f"❌ Error extrayendo Autobuses: {e}"
        
    header_mejores = "🏆 *LAS DOS MEJORES OPCIONES:*\n\n"
    if todas_opciones:
        todas_opciones.sort(key=lambda x: x["llegada"])
        for idx, opc in enumerate(todas_opciones[:2], 1):
            emoji = "🥇" if idx == 1 else "🥈"
            llegada_str = opc["llegada"].strftime('%H:%M')
            header_mejores += f"{emoji} *{opc['tipo']}* (Sale en {opc['tiempo_salida_str']} ➔ Llega a las {llegada_str})\n"
            
            for d in opc["detalles"]:
                if d["modo"] == "TRANSIT":
                    header_mejores += f"   - {d['duracion']} min - {d['linea']} ({d['origen']} ➔ {d['destino']})\n"
                elif d["modo"] == "WALK" and d["duracion"] > 0:
                    header_mejores += f"   - 🚶‍♂️ {d['duracion']} min - {d['instruccion']}\n"
            header_mejores += "\n"
    else:
         header_mejores += "No hay opciones de viaje disponibles.\n\n"
         
    mensaje_final = header_mejores + "---\n\n" + bloque_transportes

    bot.broadcast(mensaje_final.strip())
    print("Broadcast completado exitosamente.")
