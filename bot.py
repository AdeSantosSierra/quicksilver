import os
import json
import logging
import requests
import datetime
import copy
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

    def abreviar(texto):
        if not texto: return ""
        reemplazos = {
            "Majadahonda": "Maj.",
            "Intercambiador Moncloa": "Moncloa",
            "Principe Pio": "PPio",
            "Príncipe Pío": "PPio",
            "Alonso Martinez": "A. Martinez",
            "Alonso Martínez": "A. Martinez",
            "J.Rodrigo-Hospital Puerta de Hierro": "Pta. Hierro",
            "Escuela Universitaria de Estadistica": "Esc. Estadistica",
            "Estación de Tren Cercanías": "Cercanías",
            "Transbordo / Andar": "Andar"
        }
        for k, v in reemplazos.items():
            texto = texto.replace(k, v)
        # Recortar textos inútilmente largos de Google como "Villalba -Aeropuerto-T4"
        if "-" in texto and len(texto) > 20: 
            texto = texto.split("-")[0].strip()
        return texto
    
    # 1. Trenes de Cercanías
    try:
        c = Cercanias()
        trenes = c.obtener_proximos_trenes_madrid()
        
        rutas_trenes_mapa = rg.obtener_tiempo_transito_neto("estacion")
        
        # Determine the "general" line purely for the section header
        if not trenes:
            bloque_transportes += "⚠️ *Cercanías Majadahonda*\nNo hay trenes próximos hacia Madrid.\n\n"
        else:
            # Pick a fallback route for the header
            fallback_ruta = list(rutas_trenes_mapa.values())[0] if isinstance(rutas_trenes_mapa, dict) and rutas_trenes_mapa else {"tiempo": "", "ruta": ""}
            
            # Formateamos cabecera basándonos en la primera ruta si es posible
            tiempo_header = fallback_ruta.get("tiempo", "")
            ruta_str_resumen = fallback_ruta.get("ruta", "")
            
            if tiempo_header:
                bloque_transportes += f"🚆 *Cercanías (~{tiempo_header})*\n"
            else:
                bloque_transportes += f"🚆 *Cercanías*\n"
            
            for t in trenes[:3]:
                linea_tren = t['linea']
                tiempo = f"{t['minutos_restantes']}m" if t['minutos_restantes'] > 0 else "Ahora"
                
                # Fetch route specifics for this exact train line
                if isinstance(rutas_trenes_mapa, dict):
                    ruta_especifica = rutas_trenes_mapa.get(linea_tren, fallback_ruta)
                else:
                    ruta_especifica = fallback_ruta
                    
                tiempo_ruta = ruta_especifica.get("tiempo", "")
                minutos_ruta = extraer_minutos(tiempo_ruta)
                detalles_ruta = ruta_especifica.get("detalles", [])
                ruta_str = ruta_especifica.get("ruta", "")
                
                texto_llegada_suanzes = ""
                if minutos_ruta > 0 and t['minutos_restantes'] >= 0:
                    llegada_dt = ahora + datetime.timedelta(minutes=t['minutos_restantes'] + minutos_ruta)
                    texto_llegada_suanzes = f" ➔ Llega {llegada_dt.strftime('%H:%M')}"
                    
                    todas_opciones.append({
                        "tipo": "🚆 Cercanías",
                        "llegada": llegada_dt,
                        "tiempo_salida_str": tiempo,
                        "min_restantes": t['minutos_restantes'],
                        "linea": linea_tren,
                        "tiempo_trayecto": tiempo_ruta,
                        "detalles": detalles_ruta,
                        "hora_original": t['hora_original']
                    })
                    
                bloque_transportes += f"• {t['hora_original']} ({tiempo}) - {linea_tren}{texto_llegada_suanzes}\n"
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
            texto_viaje_bus = f"(~{tiempo_viaje_bus})" if tiempo_viaje_bus else ""
            
            bloque_transportes += f"🚌 *{nombre} {texto_viaje_bus}*\n"
                
            if not tiempos_buses:
                bloque_transportes += "No hay buses próximos.\n\n"
            else:
                for t in tiempos_buses[:limite]:
                    tiempo = f"{t['minutos_restantes']}m" if t['minutos_restantes'] > 0 else "Ahora"
                    
                    texto_llegada_suanzes = ""
                    if minutos_viaje_bus > 0 and t['minutos_restantes'] >= 0:
                        llegada_dt = ahora + datetime.timedelta(minutes=t['minutos_restantes'] + minutos_viaje_bus)
                        texto_llegada_suanzes = f" ➔ Llega {llegada_dt.strftime('%H:%M')}"
                        
                        detalles_reales = copy.deepcopy(detalles_bus)
                        for d in detalles_reales:
                            if d["modo"] == "TRANSIT":
                                d["linea"] = t['linea']
                                break
                                
                        todas_opciones.append({
                            "tipo": f"🚌 {nombre}",
                            "llegada": llegada_dt,
                            "tiempo_salida_str": tiempo,
                            "min_restantes": t['minutos_restantes'],
                            "linea": t['linea'],
                            "tiempo_trayecto": tiempo_viaje_bus,
                            "detalles": detalles_reales,
                            "hora_original": t['hora_llegada']
                        })
                        
                    bloque_transportes += f"• {t['hora_llegada']} ({tiempo}) - {t['linea']}{texto_llegada_suanzes}\n"
                bloque_transportes += "\n"
    except Exception as e:
        bloque_transportes += f"❌ Error extrayendo Autobuses: {e}"
        
    header_mejores = "🏆 *LAS TRES MEJORES OPCIONES:*\n\n"
    if todas_opciones:
        todas_opciones.sort(key=lambda x: x["llegada"])
        for idx, opc in enumerate(todas_opciones[:3], 1):
            if idx == 1: emoji = "🥇"
            elif idx == 2: emoji = "🥈"
            else: emoji = "🥉"
            llegada_str = opc["llegada"].strftime('%H:%M')
            header_mejores += f"{emoji} *{opc['tipo']}*\n"
            
            salida_formato = opc['tiempo_salida_str'].replace(" min", "m")
            header_mejores += f"⏳ Sale en: {salida_formato}\n"
            header_mejores += f"🏁 Llega a: {llegada_str} (⏱️ {opc['tiempo_trayecto']})\n"
            
            for d in opc["detalles"]:
                if d["modo"] == "TRANSIT":
                    o_abrv = abreviar(d['origen'])
                    d_abrv = abreviar(d['destino'])
                    header_mejores += f"  ↓ {d['duracion']}m • {d['linea']} ({o_abrv} ➔ {d_abrv})\n"
                elif d["modo"] == "WALK" and d["duracion"] > 0:
                    instr_abrv = abreviar(d['instruccion'])
                    header_mejores += f"  🚶 {d['duracion']}m • {instr_abrv}\n"
            header_mejores += "\n"
    else:
         header_mejores += "No hay opciones de viaje disponibles.\n\n"
         
    mensaje_final = header_mejores + "---\n\n" + bloque_transportes

    bot.broadcast(mensaje_final.strip())
    print("Broadcast completado exitosamente.")
