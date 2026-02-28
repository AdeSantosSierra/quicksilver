import unittest
from datetime import datetime, timedelta
from cercanias import Cercanias

class TestCercaniasTiempoRestante(unittest.TestCase):
    def setUp(self):
        self.c = Cercanias()
        self.ahora = datetime.now()

    def test_tiempo_relativo(self):
        self.assertEqual(self.c._calcular_tiempo_restante("2 min"), 2)
        self.assertEqual(self.c._calcular_tiempo_restante("14 MIN"), 14)
        self.assertEqual(self.c._calcular_tiempo_restante(" 5 min "), 5)

    def test_tiempo_absoluto_mismo_dia_futuro(self):
        # 2 horas en el futuro
        futuro = self.ahora + timedelta(hours=2, minutes=15)
        hora_str = futuro.strftime("%H:%M")
        
        # Hay que tener en cuenta que el cálculo descarta segundos, 
        # así que damos un margen de error a la aserción o simulamos todo.
        # En _calcular_tiempo_restante usa datetime.now() interamente, 
        # así que es mejor mockear o dar tolerancia.
        
        res = self.c._calcular_tiempo_restante(hora_str)
        self.assertTrue(134 <= res <= 136, f"Se esperaba ~135mins, obtuvo {res}")

    def test_tiempo_absoluto_dia_siguiente(self):
        # Que pase mañana (ej. son las 23:00 y es a la 01:00)
        # Para forzar esto, pedimos una hora de hace 22 horas (que el script leerá como mañana)
        futuro_manana = self.ahora + timedelta(hours=22)
        hora_str = futuro_manana.strftime("%H:%M")
        
        res = self.c._calcular_tiempo_restante(hora_str)
        self.assertTrue(1319 <= res <= 1321, f"Se esperaba ~1320mins, obtuvo {res}")
        
    def test_tiempo_invalido(self):
        self.assertEqual(self.c._calcular_tiempo_restante("no_time"), -1)
        self.assertEqual(self.c._calcular_tiempo_restante("24:99"), -1)

if __name__ == "__main__":
    unittest.main()
