import os
import json
import logging
import datetime
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from cercanias import Cercanias
from buses import Buses
import dgt_cameras

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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

async def send_transport_update(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    logging.info("Extrayendo datos de la web de Adif y CRTM...")
    bloque_transportes = ""
    ahora = datetime.datetime.now()
    
    # 1. Cercanías
    try:
        c = Cercanias()
        trenes = c.obtener_proximos_trenes_madrid()
        
        # Filtro extra para Alberto: Solo trenes que pasen por el andén 1 (dirección Príncipe Pío)
        trenes_anden_1 = [t for t in trenes if str(t.get('anden', '')).strip() == '1']
        
        bloque_transportes += f"🚆 *Cercanías*\n"
        if not trenes_anden_1:
            bloque_transportes += "No hay trenes próximos hacia Príncipe Pío (Andén 1).\n\n"
        else:
            for t in trenes_anden_1[:5]:
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
        
    logging.info(f"Enviando texto a {chat_id}...")
    await context.bot.send_message(chat_id=chat_id, text=bloque_transportes.strip(), parse_mode="Markdown")
    
    # 3. DGT Cameras
    logging.info("Extrayendo cámaras de la DGT...")
    await context.bot.send_message(chat_id=chat_id, text="📷 Obteniendo cámaras de la DGT A6, un segundo, por favor...")
    try:
        urls = dgt_cameras.get_dgt_cams()
        if urls:
            collage_path = "dgt_collage.jpg"
            if dgt_cameras.create_collage(urls, output_path=collage_path):
                with open(collage_path, "rb") as photo:
                    await context.bot.send_photo(chat_id=chat_id, photo=photo, caption="📷 *Cámaras DGT (A-6)*", parse_mode="Markdown")
            else:
                logging.error("No se pudo crear el collage.")
        else:
            logging.error("No se encontraron URLs de cámaras DGT.")
    except Exception as e:
        logging.error(f"Error procesando cámaras DGT: {e}")

async def send_transport_update_ana(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    logging.info("Extrayendo datos de la web de Adif y CRTM para /ana...")
    bloque_transportes = ""
    ahora = datetime.datetime.now()
    
    # 1. Cercanías Específico
    try:
        c = Cercanias(url="https://www.adif.es/-/10001-aravaca")
        trenes = c.obtener_proximos_trenes_madrid()
        
        # Filtro extra para Ana: Solo trenes que pasen por el andén 1 (dirección Príncipe Pío)
        trenes_anden_1 = [t for t in trenes if str(t.get('anden', '')).strip() == '1']
        
        bloque_transportes += f"🚆 *Cercanías (Aravaca)*\n"
        if not trenes_anden_1:
            bloque_transportes += "No hay trenes próximos hacia Príncipe Pío (Andén 1).\n\n"
        else:
            for t in trenes_anden_1[:5]:
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
            {"id": "11980", "nombre": "Parada 11980", "limite": 5},
            {"id": "02419", "nombre": "Parada 02419", "limite": 5},
            {"id": "17480", "nombre": "Parada 17480", "limite": 5},
            {"id": "09478", "nombre": "Parada 09478", "limite": 5}
        ]
        lineas_permitidas = ["160", "161", "657", "657a", "658"]
        
        for parada in paradas_config:
            id_parada = parada["id"]
            nombre = f"{parada['nombre']}"
            limite = parada["limite"]
            
            tiempos_buses_crudo = b.obtener_tiempos_parada(id_parada)
            # Filtrar por líneas permitidas
            tiempos_buses = [t for t in tiempos_buses_crudo if str(t['linea']).lower() in lineas_permitidas]
            
            bloque_transportes += f"🚌 *{nombre}*\n"
                
            if not tiempos_buses:
                bloque_transportes += "No hay buses próximos de las líneas seleccionadas.\n\n"
            else:
                for t in tiempos_buses[:limite]:
                    bloque_transportes += f"• {t['hora_llegada']} - {t['linea']}\n"
                bloque_transportes += "\n"
    except Exception as e:
        bloque_transportes += f"❌ Error extrayendo Autobuses: {e}\n\n"
        
    logging.info(f"Enviando texto a {chat_id}...")
    await context.bot.send_message(chat_id=chat_id, text=bloque_transportes.strip(), parse_mode="Markdown")
    
    # 3. DGT Cameras
    logging.info("Extrayendo cámaras de la DGT...")
    await context.bot.send_message(chat_id=chat_id, text="📷 Obteniendo cámaras de la DGT A6, un segundo, por favor...")
    try:
        urls = dgt_cameras.get_dgt_cams()
        if urls:
            collage_path = "dgt_collage.jpg"
            if dgt_cameras.create_collage(urls, output_path=collage_path):
                with open(collage_path, "rb") as photo:
                    await context.bot.send_photo(chat_id=chat_id, photo=photo, caption="📷 *Cámaras DGT (A-6)*", parse_mode="Markdown")
            else:
                logging.error("No se pudo crear el collage.")
        else:
            logging.error("No se encontraron URLs de cámaras DGT.")
    except Exception as e:
        logging.error(f"Error procesando cámaras DGT: {e}")

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
        
    await update.message.reply_text("🔄 Consultando transportes...")
    await send_transport_update(context, chat_id)

async def ana_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in suscriptores:
        suscriptores.add(chat_id)
        save_subscribers(suscriptores)
        
    await update.message.reply_text("🔄 Consultando transportes...")
    await send_transport_update_ana(context, chat_id)

if __name__ == '__main__':
    if not TOKEN:
        logging.error("No se encontró TELEGRAM_BOT_TOKEN en el entorno.")
        exit(1)
        
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("alberto", alberto_command))
    app.add_handler(CommandHandler("ana", ana_command))

    logging.info("Bot en ejecución. Pulsa Ctrl+C para salir.")
    app.run_polling()
