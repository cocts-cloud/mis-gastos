"""Cliente de la API de partners de seats.aero.

seats.aero cachea la disponibilidad de premios de varios programas de millas.
Air Europa (UX) es SkyTeam, así que sus asientos premio aparecen en los
programas socios: Flying Blue, Delta SkyMiles, Aeroméxico Club Premier, etc.
Filtramos los resultados para quedarnos con vuelos operados por UX.

Docs: https://developers.seats.aero
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict

import httpx

BASE_URL = "https://seats.aero/partnerapi"

# Programas de seats.aero que pueden emitir vuelos de Air Europa.
PROGRAMAS_SKYTEAM = ["flyingblue", "delta", "aeromexico", "virginatlantic"]

CABINAS = {"economy": "Y", "premium": "W", "business": "J", "first": "F"}


@dataclass
class Disponibilidad:
    fecha: str
    origen: str
    destino: str
    programa: str
    cabina: str
    millas: int
    asientos: int | None
    aerolineas: str
    directo: bool
    id: str
    actualizado: str

    def to_dict(self) -> dict:
        return asdict(self)


class SeatsAeroError(RuntimeError):
    pass


def _a_int(valor) -> int:
    try:
        return int(str(valor).replace(",", ""))
    except (TypeError, ValueError):
        return 0


def buscar(
    origen: str,
    destino: str,
    fecha_desde: str,
    fecha_hasta: str,
    cabina: str = "economy",
    programas: list[str] | None = None,
    aerolinea: str = "UX",
    solo_directos: bool = False,
    api_key: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> list[Disponibilidad]:
    """Busca asientos premio entre dos aeropuertos (acepta listas separadas por coma)."""
    api_key = api_key or os.environ.get("SEATS_AERO_API_KEY")
    if not api_key:
        raise SeatsAeroError("Falta SEATS_AERO_API_KEY (ver .env.example).")
    letra = CABINAS[cabina]
    params = {
        "origin_airport": origen.upper(),
        "destination_airport": destino.upper(),
        "start_date": fecha_desde,
        "end_date": fecha_hasta,
        "cabins": cabina,
        "sources": ",".join(programas or PROGRAMAS_SKYTEAM),
        "carriers": aerolinea,
        "only_direct_flights": str(solo_directos).lower(),
        "take": 1000,
    }
    headers = {"Partner-Authorization": api_key, "accept": "application/json"}

    resultados: list[Disponibilidad] = []
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=60, transport=transport) as http:
        cursor = None
        while True:
            if cursor:
                params["cursor"] = cursor
                params["skip"] = len(resultados)
            r = http.get("/search", params=params)
            if r.status_code == 401:
                raise SeatsAeroError("API key de seats.aero inválida o sin plan Pro.")
            if r.status_code == 429:
                raise SeatsAeroError("Límite diario de la API de seats.aero alcanzado.")
            r.raise_for_status()
            cuerpo = r.json()
            for fila in cuerpo.get("data", []):
                if not fila.get(f"{letra}Available"):
                    continue
                aerolineas = fila.get(f"{letra}Airlines") or ""
                # El filtro "carriers" del servidor no siempre es exacto: confirmamos acá.
                if aerolinea and aerolinea.upper() not in aerolineas.upper():
                    continue
                ruta = fila.get("Route", {})
                resultados.append(
                    Disponibilidad(
                        fecha=fila.get("Date", "")[:10],
                        origen=ruta.get("OriginAirport", ""),
                        destino=ruta.get("DestinationAirport", ""),
                        programa=fila.get("Source") or ruta.get("Source", ""),
                        cabina=cabina,
                        millas=_a_int(fila.get(f"{letra}MileageCost")),
                        asientos=fila.get(f"{letra}RemainingSeats") or None,
                        aerolineas=aerolineas,
                        directo=bool(fila.get(f"{letra}Direct")),
                        id=fila.get("ID", ""),
                        actualizado=fila.get("UpdatedAt", ""),
                    )
                )
            if not cuerpo.get("hasMore") or not cuerpo.get("cursor"):
                break
            cursor = cuerpo["cursor"]
    resultados.sort(key=lambda d: (d.millas, d.fecha))
    return resultados


def detalle_vuelos(disponibilidad_id: str, api_key: str | None = None) -> list[dict]:
    """Devuelve los itinerarios (vuelos, horarios, escalas) de una disponibilidad."""
    api_key = api_key or os.environ.get("SEATS_AERO_API_KEY")
    if not api_key:
        raise SeatsAeroError("Falta SEATS_AERO_API_KEY (ver .env.example).")
    r = httpx.get(
        f"{BASE_URL}/trips/{disponibilidad_id}",
        headers={"Partner-Authorization": api_key, "accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    viajes = []
    for t in r.json().get("data", []):
        viajes.append(
            {
                "vuelos": t.get("FlightNumbers"),
                "cabina": t.get("Cabin"),
                "millas": t.get("MileageCost"),
                "tasas": f'{t.get("TotalTaxes", 0) / 100:.2f} {t.get("TaxesCurrency", "")}'.strip(),
                "salida": t.get("DepartsAt"),
                "llegada": t.get("ArrivesAt"),
                "escalas": t.get("Stops"),
                "duracion_min": t.get("TotalDuration"),
                "asientos": t.get("RemainingSeats"),
            }
        )
    return viajes
