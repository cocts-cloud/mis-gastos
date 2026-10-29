"""Búsqueda directa (sin IA) de vuelos premio de Air Europa.

Ejemplos:
  python buscar.py seats --origen EZE --destino MAD --desde 2027-07-01 --hasta 2027-07-31 --cabina business
  python buscar.py capturar
  python buscar.py repetir --desde 2027-07-01 --hasta 2027-07-31
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from fuentes import air_europa_web, seats_aero

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
    s.add_argument("--origen", required=True, help="IATA, o varios separados por coma: EZE,MVD")
    s.add_argument("--destino", required=True, help="IATA, o varios: MAD,BCN")
    s.add_argument("--desde", default="2027-07-01")
    s.add_argument("--hasta", default="2027-07-31")
    s.add_argument("--cabina", default="economy", choices=list(seats_aero.CABINAS))
    s.add_argument("--programas", default=",".join(seats_aero.PROGRAMAS_SKYTEAM))
    s.add_argument("--directos", action="store_true")
    s.add_argument("--json", action="store_true", help="Imprimir JSON en vez de tabla")

    sub.add_parser("capturar", help="Abrir aireuropa.com y capturar una búsqueda con millas SUMA")

    r = sub.add_parser("repetir", help="Repetir la búsqueda SUMA capturada en un rango de fechas")
    r.add_argument("--desde", default="2027-07-01")
    r.add_argument("--hasta", default="2027-07-31")
    r.add_argument("--pausa", type=float, default=6.0, help="Segundos entre consultas")

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
        air_europa_web.capturar()
        return
    else:
        filas = air_europa_web.repetir(a.desde, a.hasta, a.pausa)
        imprimir(filas, ["fecha", "millas", "vuelo", "cabina", "tasas"])
        ruta = guardar(f"suma_{a.desde}_{a.hasta}", filas)
    if ruta:
        print(f"\nCSV: {ruta}")


if __name__ == "__main__":
    main()
