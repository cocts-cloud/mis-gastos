"""Búsqueda directa (sin IA) de vuelos premio de Air Europa.

Los valores por defecto (Córdoba -> Valencia, ida 24-30/06, vuelta hasta 15/07/2027, 70.100 millas)
salen de config.py.

Millas SUMA (aireuropa.com):
  python buscar.py capturar --tramo ida      # buscás a mano COR -> VLC solo ida, pagando con millas
  python buscar.py capturar --tramo vuelta   # buscás a mano VLC -> COR solo ida, pagando con millas
  python buscar.py repetir --tramo ida
  python buscar.py repetir --tramo vuelta
  python buscar.py combinar --min-dias 10    # pares ida+vuelta que entran en tu saldo

Socios SkyTeam (seats.aero):
  python buscar.py seats --cabina business
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import config
from fuentes import air_europa_web, seats_aero
from fuentes.combinar import combinar

RESULTADOS = Path(__file__).resolve().parent / "resultados"


def cargar_env() -> None:
    env = Path(__file__).resolve().parent / ".env"
    if env.exists():
        for linea in env.read_text().splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def guardar(nombre: str, filas: list[dict]) -> Path | None:
    if not filas:
        return None
    RESULTADOS.mkdir(exist_ok=True)
    ruta = RESULTADOS / f"{nombre}.csv"
    with ruta.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    return ruta


def leer(nombre: str) -> list[dict]:
    ruta = RESULTADOS / f"{nombre}.csv"
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}. Corré antes: python buscar.py repetir --tramo {nombre.removeprefix('suma_')}")
    with ruta.open() as f:
        return list(csv.DictReader(f))


def imprimir(filas: list[dict], columnas: list[str], limite: int = 40) -> None:
    if not filas:
        print("Sin disponibilidad para esos criterios.")
        return
    anchos = {c: max(len(c), *(len(str(f.get(c, ""))) for f in filas[:limite])) for c in columnas}
    print("  ".join(c.ljust(anchos[c]) for c in columnas))
    for f in filas[:limite]:
        print("  ".join(str(f.get(c, "")).ljust(anchos[c]) for c in columnas))
    if len(filas) > limite:
        print(f"... y {len(filas) - limite} más (ver CSV)")


def main() -> None:
    cargar_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("seats", help="Buscar en seats.aero (Flying Blue, Delta, etc.)")
    s.add_argument("--origen", default=config.ORIGEN, help="IATA, o varios separados por coma: COR,EZE")
    s.add_argument("--destino", default=config.DESTINO, help="IATA, o varios: VLC,MAD")
    s.add_argument("--desde", default=config.VENTANA_DESDE)
    s.add_argument("--hasta", default=config.VENTANA_HASTA)
    s.add_argument("--cabina", default="economy", choices=list(seats_aero.CABINAS))
    s.add_argument("--programas", default=",".join(seats_aero.PROGRAMAS_SKYTEAM))
    s.add_argument("--directos", action="store_true")
    s.add_argument("--json", action="store_true", help="Imprimir JSON en vez de tabla")

    c = sub.add_parser("capturar", help="Abrir aireuropa.com y capturar una búsqueda con millas SUMA")
    c.add_argument("--tramo", default="ida", choices=["ida", "vuelta"])

    r = sub.add_parser("repetir", help="Repetir la búsqueda SUMA capturada en un rango de fechas")
    r.add_argument("--tramo", default="ida", choices=["ida", "vuelta"])
    r.add_argument("--desde", help="Por defecto: ida IDA_DESDE, vuelta IDA_DESDE (config.py)")
    r.add_argument("--hasta", help="Por defecto: ida IDA_HASTA, vuelta VUELTA_HASTA (config.py)")
    r.add_argument("--pausa", type=float, default=6.0, help="Segundos entre consultas")

    k = sub.add_parser("combinar", help="Combinar ida y vuelta SUMA dentro del saldo de millas")
    k.add_argument("--millas", type=int, default=config.MILLAS_DISPONIBLES)
    k.add_argument("--min-dias", type=int, default=1)
    k.add_argument("--max-dias", type=int, default=None)

    a = ap.parse_args()
    if a.cmd == "seats":
        filas = [
            d.to_dict()
            for d in seats_aero.buscar(
                a.origen, a.destino, a.desde, a.hasta, a.cabina, a.programas.split(","), solo_directos=a.directos
            )
        ]
        if a.json:
            print(json.dumps(filas, ensure_ascii=False, indent=2))
        else:
            imprimir(filas, ["fecha", "origen", "destino", "programa", "millas", "asientos", "aerolineas", "directo"])
        ruta = guardar(f"seats_{a.origen}-{a.destino}_{a.desde}_{a.hasta}_{a.cabina}".replace(",", "+"), filas)
    elif a.cmd == "capturar":
        air_europa_web.capturar(a.tramo)
        return
    elif a.cmd == "repetir":
        desde = a.desde or config.IDA_DESDE
        hasta = a.hasta or (config.IDA_HASTA if a.tramo == "ida" else config.VUELTA_HASTA)
        filas = air_europa_web.repetir(desde, hasta, a.pausa, a.tramo)
        imprimir(filas, ["fecha", "millas", "vuelo", "cabina", "tasas"])
        ruta = guardar(f"suma_{a.tramo}", filas)
    else:
        filas = combinar(leer("suma_ida"), leer("suma_vuelta"), a.millas, a.min_dias, a.max_dias)
        print(f"Saldo: {a.millas:,} millas\n".replace(",", "."))
        imprimir(filas, ["ida", "vuelta", "dias", "millas_ida", "millas_vuelta", "total", "sobran"])
        ruta = guardar("suma_combinaciones", filas)
    if ruta:
        print(f"\nCSV: {ruta}")


if __name__ == "__main__":
    main()
