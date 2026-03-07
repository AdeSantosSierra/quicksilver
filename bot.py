import os
import json
import logging
import datetime
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Mongo setup
try:
    if MONGO_URI:
        mongo_client = MongoClient(MONGO_URI)
        mongo_db = mongo_client['transporte_db']
        extracciones = mongo_db['extracciones']
    else:
        logging.error("MONGO_URI no está definido en el .env")
        extracciones = None
except Exception as e:
    logging.error(f"Error conectando a Mongo en bot: {e}")
    extracciones = None

SUBSCRIBERS_FILE = "subscribers.json"

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r") as f:
                return set(json.load(f))
        except json.JSONDecodeError:
            return set()
    return set()

def save_subscribers(subs):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(list(subs), f)

suscriptores = load_subscribers()

def format_minutos(minutos_val):
    try:
        m = int(minutos_val)
        if m >= 60:
            h = m // 60
            rest = m % 60
            if rest == 0:
                return f"{h}h"
            return f"{h}h {rest}min"
        return f"{m} min"
    except (ValueError, TypeError):
        return "?"

def format_metro_frecuencia(frec):
    if frec is None: return "frec. variable"
    try:
        frec = float(frec)
        if frec == int(frec):
            return f"{int(frec)} min"
        # Si tiene decimales, mostramos rango
        low = int(frec)
        high = low + 1
        return f"{low}-{high} min"
    except:
        return "frec. variable"

def get_latest_transport_data(parada_id: str, limit: int = 5, lineas_permitidas: list = None, unique_lines: bool = False):
    if extracciones is None:
        return []
    
    query = {"parada": parada_id}
    
    # Encontrar el timestamp más reciente para esta parada
    latest_doc = extracciones.find_one({"parada": parada_id}, sort=[("timestamp", -1)])
    if not latest_doc:
        return []
        
    latest_ts = latest_doc["timestamp"]
    query["timestamp"] = latest_ts
    
    if lineas_permitidas:
        # El collector extrajo el campo 'shortDescription' que puede ser cosas como '657A'.
        # Tenemos que hacer matches EXACTOS (regex con ^ y $) para cada linea permitida.
        regex_list = [{"linea": {"$regex": f"^{linea}$", "$options": "i"}} for linea in lineas_permitidas]
        query["$or"] = regex_list
    
    results_raw = list(extracciones.find(query).sort("minutos_restantes", 1))
    
    # Filter duplicates and fix exact hour
    results = []
    seen = set()
    ahora_dt = datetime.datetime.now()
    
    for r in results_raw:
        # 1. Recalcular minutos reales respecto a 'ahora'
        mins_orig = r.get("minutos_restantes")
        if mins_orig == -999:
            # Es un aviso de incidencia, lo mantenemos tal cual
            real_mins = -999
        else:
            # Calcular cuánto tiempo ha pasado desde que se extrajo el dato
            delta_mins = int((ahora_dt - latest_ts).total_seconds() / 60)
            real_mins = mins_orig - delta_mins
            
            # Si el bus ya pasó hace más de 2 minutos, lo ignoramos
            if real_mins < -2:
                continue
            # No mostrar negativos feos en la UI, mínimo 0
            r["minutos_restantes"] = max(0, real_mins)

        if unique_lines:
            # Only 1 bus per line
            ident = r.get("linea")
        else:
            # Exact deduplication
            ident = (r.get("linea"), r.get("destino"), r.get("hora_llegada"))

        if ident not in seen:
            seen.add(ident)
            
            # Formatear siempre hora_llegada como HH:MM si solo trae minutos
            hora = str(r.get("hora_llegada", ""))
            if ":" not in hora and real_mins != -999:
                # Si recalculo la hora aquí, será sobre el latest_ts + mins_originales
                exact_time = latest_ts + datetime.timedelta(minutes=int(mins_orig))
                r["hora_llegada"] = exact_time.strftime("%H:%M")
                
            results.append(r)
            if len(results) >= limit:
                break
                
    return results

async def send_transport_update(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    logging.info("Consultando transportes desde MongoDB para /alberto...")
    bloque_transportes = ""
    
    # 1. Cercanías (Majadahonda -> 'Majadaho')
    try:
        # El collector ya insertó solo los de Andén 1 o Majadahonda general.
        # En la lógica anterior, Alberto quería trenes de Majadahonda (Andén 1).
        # El collector guardó the 'anden'. Filtrémoslo aquí.
        trenes = get_latest_transport_data("Majadaho", limit=50)
        trenes_madrid = [t for t in trenes if str(t.get('anden', '')).strip() == '1']
        
        bloque_transportes += f"🚆 *Cercanías*\n"
        if not trenes_madrid:
            bloque_transportes += "No hay trenes próximos hacia Madrid.\n\n"
        else:
            for t in trenes_madrid[:5]:
                minutos_formateados = format_minutos(t.get('minutos_restantes')); bloque_transportes += f"• {t['hora_llegada']} ({minutos_formateados}) - {t['linea']}\n"
            bloque_transportes += "\n"
    except Exception as e:
        bloque_transportes += f"❌ Error leyendo Cercanías: {e}\n\n"


    # 3. Autobuses Interurbanos
    try:
        paradas_config = [
            {"id": "00017699", "nombre": "Farmacia Rotonda FGL (17699)", "limite": 3},
            {"id": "00007305", "nombre": "Estación sentido Madrid (07305)", "limite": 3}
        ]
        
        for parada in paradas_config:
            id_parada = parada["id"]
            nombre = parada['nombre']
            limite = parada["limite"]
            
            buses = get_latest_transport_data(id_parada, limit=limite)
            bloque_transportes += f"🚌 *{nombre}*\n"
                
            if not buses:
                bloque_transportes += "No hay buses próximos.\n\n"
            else:
                for t in buses[:limite]:
                    minutos_formateados = format_minutos(t.get('minutos_restantes')); bloque_transportes += f"• {t['hora_llegada']} ({minutos_formateados}) - {t['linea']}\n"
                bloque_transportes += "\n"
    except Exception as e:
        bloque_transportes += f"❌ Error leyendo Autobuses: {e}"
        
    # 4. Metro (Líneas Personalizadas - Al Final)
    try:
        # Alberto: L3, L4, L10, L5
        metro_configs = [
            {"id": "4_53", "lineas": ["3"]},
            {"id": "4_9", "lineas": ["4"]},
            {"id": "4_1", "lineas": ["10"]},
            {"id": "4_96", "lineas": ["5"]}
        ]
        
        bloque_metro = ""
        for conf in metro_configs:
            m_data = get_latest_transport_data(conf["id"], lineas_permitidas=conf["lineas"], limit=3)
            if not m_data: continue
            
            first = m_data[0]
            l_name = first['linea']
            if first.get('minutos_restantes') == -999:
                bloque_metro += f"• L{l_name}: ⚠️ _Corte o demora grave_\n"
            else:
                f_str = format_metro_frecuencia(first.get("frecuencia_media"))
                bloque_metro += f"• L{l_name}: Cada {f_str}\n"
        
        if bloque_metro:
            bloque_transportes += "\n🚇 *Metro*\n" + bloque_metro

    except Exception as e:
        bloque_transportes += f"\n❌ Error leyendo Metro: {e}"

    logging.info(f"Enviando texto a {chat_id}...")
    await context.bot.send_message(chat_id=chat_id, text=bloque_transportes.strip(), parse_mode="Markdown")
    
    # 5. DGT Cameras
    logging.info("Enviando foto de cámaras DGT desde disco...")
    try:
        collage_path = "dgt_collage.jpg"
        if os.path.exists(collage_path):
            with open(collage_path, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption="📷 *Cámaras DGT (A-6)*", parse_mode="Markdown")
        else:
            logging.error("El collage DGT no existe en disco aún.")
    except Exception as e:
        logging.error(f"Error procesando cámaras DGT desde disco: {e}")

async def send_transport_update_ana(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    logging.info("Consultando transportes desde MongoDB para /ana...")
    bloque_transportes = ""
    
    # 1. Cercanías (Aravaca -> 'Aravaca0')
    try:
        trenes = get_latest_transport_data("Aravaca0", limit=50)
        trenes_madrid = [t for t in trenes if str(t.get('anden', '')).strip() == '2']
        
        bloque_transportes += f"🚆 *Cercanías (Aravaca)*\n"
        if not trenes_madrid:
            bloque_transportes += "No hay trenes próximos hacia Madrid.\n\n"
        else:
            for t in trenes_madrid[:5]:
                minutos_formateados = format_minutos(t.get('minutos_restantes')); bloque_transportes += f"• {t['hora_llegada']} ({minutos_formateados}) - {t['linea']}\n"
            bloque_transportes += "\n"
    except Exception as e:
        bloque_transportes += f"❌ Error leyendo Cercanías: {e}\n\n"


    # 3. Autobuses Interurbanos
    try:
        paradas_config = [
            {"id": "00011980", "nombre": "Parada 11980", "limite": 5},
            {"id": "00002419", "nombre": "Parada 02419", "limite": 5},
            {"id": "00017480", "nombre": "Parada 17480", "limite": 5},
            {"id": "00009478", "nombre": "Parada 09478", "limite": 5}
        ]
        lineas_permitidas = ["160", "161", "657", "657a", "658"]
        
        for parada in paradas_config:
            id_parada = parada["id"]
            nombre = parada["nombre"]
            limite = parada["limite"]
            
            # Enforce unique lines ONLY for 17480 as requested
            req_unique = True if id_parada == "00017480" else False
            
            buses = get_latest_transport_data(id_parada, limit=limite, lineas_permitidas=lineas_permitidas, unique_lines=req_unique)
            bloque_transportes += f"🚌 *{nombre}*\n"
                
            if not buses:
                # Format the lines string, e.g., "160, 161, 657, 657a o 658"
                if len(lineas_permitidas) > 1:
                    lineas_str = ", ".join(lineas_permitidas[:-1]) + " o " + lineas_permitidas[-1]
                elif lineas_permitidas:
                    lineas_str = lineas_permitidas[0]
                else:
                    lineas_str = "seleccionadas"
                    
                bloque_transportes += f"No hay buses próximos de las líneas {lineas_str}.\n\n"
            else:
                for t in buses[:limite]:
                    minutos_formateados = format_minutos(t.get('minutos_restantes')); bloque_transportes += f"• {t['hora_llegada']} ({minutos_formateados}) - {t['linea']}\n"
                bloque_transportes += "\n"
    except Exception as e:
        bloque_transportes += f"❌ Error leyendo Autobuses: {e}\n\n"
        
    # 4. Metro (Ana: Solo L5 - Al Final)
    try:
        m_data = get_latest_transport_data("4_96", lineas_permitidas=["5"], limit=3)
        if m_data:
            first = m_data[0]
            l_name = first['linea']
            if first.get('minutos_restantes') == -999:
                bloque_transportes += f"\n🚇 *Metro*\n• L{l_name}: ⚠️ _Corte o demora grave_"
            else:
                f_str = format_metro_frecuencia(first.get("frecuencia_media"))
                bloque_transportes += f"\n🚇 *Metro*\n• L{l_name}: Cada {f_str}"
    except Exception as e:
        bloque_transportes += f"\n❌ Error leyendo Metro: {e}"

    logging.info(f"Enviando texto a {chat_id}...")
    await context.bot.send_message(chat_id=chat_id, text=bloque_transportes.strip(), parse_mode="Markdown")
    
    # 5. DGT Cameras
    logging.info("Enviando foto de cámaras DGT desde disco para Ana...")
    try:
        collage_path = "dgt_collage.jpg"
        if os.path.exists(collage_path):
            with open(collage_path, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption="📷 *Cámaras DGT (A-6)*", parse_mode="Markdown")
        else:
            logging.error("El collage DGT no existe en disco aún.")
    except Exception as e:
        logging.error(f"Error procesando cámaras DGT desde disco: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in suscriptores:
        suscriptores.add(chat_id)
        save_subscribers(suscriptores)
    await update.message.reply_text("¡Hola! Soy CorrecaminosBot. Usa /alberto o /ana para recibir el estado del transporte al instante.")

async def alberto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in suscriptores:
        suscriptores.add(chat_id)
        save_subscribers(suscriptores)
        
    # The response is now nearly instantaneous! Wait, DGT cameras take ~5s. Let's send the text anyway so the user knows it's working instantly.
    # Actually wait, send_transport_update sends the text, then the image.
    await send_transport_update(context, chat_id)

async def ana_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in suscriptores:
        suscriptores.add(chat_id)
        save_subscribers(suscriptores)
        
    await send_transport_update_ana(context, chat_id)

if __name__ == '__main__':
    if not TOKEN:
        logging.error("No se encontró TELEGRAM_BOT_TOKEN en el entorno.")
        exit(1)
        
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("alberto", alberto_command))
    app.add_handler(CommandHandler("ana", ana_command))

    logging.info("Bot en ejecución usando MongoDB. Pulsa Ctrl+C para salir.")
    app.run_polling()
