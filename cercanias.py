import re
from datetime import datetime, timedelta
from typing import List, Dict, Union
from playwright.sync_api import sync_playwright

class Cercanias:
    def __init__(self, url: str = "https://www.adif.es/w/10007-majadahonda", page = None):
        self.url = url
        self.page = page

    def _calcular_tiempo_restante(self, hora_str: str) -> int:
        """
        Calcula el tiempo restante en minutos a partir de un string.
        Puede ser relativo ('2 min') o absoluto ('14:30', '14:30 h').
        Devuelve -1 si no puede parsear.
        """
        hora_str = hora_str.strip().lower()
        
        # Caso relativo: "2 min", "1 min"
        match_relativo = re.search(r'(\d+)\s*min', hora_str)
        if match_relativo:
            return int(match_relativo.group(1))
        
        # Caso absoluto: "14:30", "14:30 h"
        match_absoluto = re.search(r'(\d{1,2}):(\d{2})', hora_str)
        if match_absoluto:
            horas = int(match_absoluto.group(1))
            mins = int(match_absoluto.group(2))
            
            ahora = datetime.now()
            try:
                hora_tren = ahora.replace(hour=horas, minute=mins, second=0, microsecond=0)
            except ValueError:
                # Hora o minuto fuera de rango
                return -1
            
            # Si el tren es más tarde ese día, la diferencia es positiva.
            # Pero si la diferencia es muy negativa (ej. tren 01:00, ahora 23:00)
            # es porque el tren es mañana.
            if hora_tren < ahora and (ahora - hora_tren).total_seconds() > 3600 * 2:
                hora_tren += timedelta(days=1)
                
            diferencia_mins = int((hora_tren - ahora).total_seconds() / 60)
            if diferencia_mins < 0:
                # Si es dentro de la última hora, consideramos 0 para indicar "ahora"
                if diferencia_mins > -60:
                    return 0
                return -1 # Pasado hace más de 1 hora
            return diferencia_mins
            
        return -1

    def obtener_proximos_trenes(self) -> List[Dict[str, Union[str, int]]]:
        """
        Devuelve una lista de diccionarios con la información de los próximos trenes.
        Si la clase fue inicializada con un 'page' de Playwright inyectado,
        lo reúsamos directamente de forma síncrona. Si no, lanzamos uno por nuestro lado.
        """
        if self.page:
            return self._obtener_proximos_trenes_sync(self.page)
        else:
            # Fallback en caso de que alguien llame a Cercanias() instanciándolo tal cual
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(self._obtener_proximos_trenes_standalone).result()

    def _obtener_proximos_trenes_standalone(self) -> List[Dict[str, Union[str, int]]]:
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            resultados = self._obtener_proximos_trenes_sync(page)
            browser.close()
            return resultados

    def _obtener_proximos_trenes_sync(self, page) -> List[Dict[str, Union[str, int]]]:
        resultados = []
        try:
            page.goto(self.url, wait_until="networkidle", timeout=30000)
            
            # Esperar a que los elementos del horario estén visibles para mayor robustez
            page.wait_for_selector("tr.horario-row.cercanias", state="attached", timeout=30000)
            
            # Extraer usando locators (traspasa Shadow DOM si lo hay)
            rows = page.locator("tr.horario-row.cercanias").all()
            
            for row in rows:
                try:
                    hora = row.locator(".col-hora span").first.text_content(timeout=5000).strip()
                    destino_loc = row.locator(".col-destino a")
                    if destino_loc.count() > 0:
                        destino = destino_loc.first.text_content(timeout=5000).strip()
                    else:
                        destino = row.locator(".col-destino").text_content(timeout=5000).strip()
                        
                    linea = row.locator(".col-tren .lineColored").text_content(timeout=5000).strip()
                    via = row.locator(".col-via span").first.text_content(timeout=5000).strip()
                    
                    min_restantes = self._calcular_tiempo_restante(hora)
                    
                    if hora and destino:
                        resultados.append({
                            'hora_original': hora,
                            'destino': destino,
                            'linea': linea,
                            'anden': via,
                            'minutos_restantes': min_restantes
                        })
                except Exception as e:
                    print(f"Saltando fila incompleta: {e}")
                    continue
        except Exception as e:
            print(f"Error cargando o buscando elementos: {e}")
            
        return resultados

    def obtener_proximos_trenes_madrid(self) -> List[Dict[str, Union[str, int]]]:
        """
        Devuelve una lista de diccionarios con la información de los próximos trenes
        cuyo destino contenga la palabra 'Madrid'.
        """
        trenes = self.obtener_proximos_trenes()
        return [t for t in trenes if 'madrid' in str(t['destino']).lower()]

if __name__ == "__main__":
    c = Cercanias()
    print("Obteniendo datos de Adif...")
    trenes = c.obtener_proximos_trenes_madrid()
    if not trenes:
        print("No se encontraron trenes hacia Madrid o hubo un error.")
    else:
        for t in trenes:
            print(f"[{t['minutos_restantes']} min] Línea {t['linea']} hacia {t['destino']} | Andén: {t['anden']} (Hora: {t['hora_original']})")
