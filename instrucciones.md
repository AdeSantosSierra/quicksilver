# Instrucciones del Proyecto

Vamos a crear una clase, que se llamara `Cercanias` que va a leer de aquí: https://www.adif.es/w/10007-majadahonda los datos de hora, línea y andén. 
Quiero que obtenta la lista de siguientes trenes y cuánto tiempo queda para que pase el tren.

Ese dato de hora puede venir en tiempo (tipo 2 minutos, etc...) o puede venir con hora. Quiero que tengas en cuenta ambas opciones. Quiero que el código sea siemple sencillo y fácil de mantener. Quiero que sea robusto.

Puedes crear primero un entorno con venv que se llame como el repo donde sintales lo que necesites.

Todas estas instrucciones, puedes guardarlas en un MD o dodne quieras, para que yo no tenga que volver a especificarlas.

## Configuración de Despliegue en Servidor 103 (Marzo 2026)
- **Servidor**: `192.168.1.103` (Acceso SSH por puerto `45322`)
- **Directorio Raíz**: `/home/alberto/quicksilver`
- **Entorno Virtual**: `/home/alberto/quicksilver/venv`
- **Gestión de Ejecución (Persistencia)**: Utiliza `systemd` como usuario local.
  - Para ver el estado actual: `systemctl --user status quicksilver-bot.service`
  - Para reiniciarlo: `systemctl --user restart quicksilver-bot.service`
  - Para apagarlo: `systemctl --user stop quicksilver-bot.service`
  - Para ver los registros y excepciones en vivo: `journalctl --user -fu quicksilver-bot.service`
- **Filtros Actuales de Cercanías**: Los comandos `/alberto` (Majadahonda) y `/ana` (Aravaca) filtran exclusivamente los trenes que pasen por el **Andén 1** (asegurando el flujo pasante hacia Príncipe Pío / Chamartín).
