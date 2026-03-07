import time
import logging
import dgt_cameras

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

OUTPUT_PATH = "dgt_collage.jpg"

def collect_images():
    logging.info("Extrayendo cámaras de la DGT...")
    try:
        urls = dgt_cameras.get_dgt_cams()
        if urls:
            if dgt_cameras.create_collage(urls, output_path=OUTPUT_PATH):
                logging.info(f"Collage guardado exitosamente en {OUTPUT_PATH}")
            else:
                logging.error("No se pudo crear el collage.")
        else:
            logging.error("No se encontraron URLs de cámaras DGT.")
    except Exception as e:
        logging.error(f"Error procesando cámaras DGT: {e}")

def main():
    logging.info("Iniciando Image Collector daemon...")
    while True:
        logging.info("Iniciando ciclo de extracción de imágenes...")
        collect_images()
        logging.info("Ciclo terminado. Durmiendo 60 segundos...")
        time.sleep(60)

if __name__ == "__main__":
    main()
