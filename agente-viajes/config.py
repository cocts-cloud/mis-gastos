"""Datos del viaje. Cambialos acá y todo el proyecto los toma por defecto."""

ORIGEN = "COR"  # Córdoba, Argentina (Air Europa vuela directo COR-MAD)
DESTINO = "VLC"  # Valencia, España (conexión UX en Madrid)
IDA_DESDE = "2027-06-24"  # última semana de junio
IDA_HASTA = "2027-06-30"
VUELTA_HASTA = "2027-07-15"  # regreso a más tardar el 15 de julio
MILLAS_DISPONIBLES = 70_100  # saldo SUMA
PROGRAMA = "SUMA"

# Ventana completa del viaje (la usan seats.aero y el agente)
VENTANA_DESDE = IDA_DESDE
VENTANA_HASTA = VUELTA_HASTA
