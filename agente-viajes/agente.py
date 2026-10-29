"""Agente de viajes conversacional: busca vuelos de Air Europa canjeando millas.

Uso:
  python agente.py
  python agente.py "Quiero ir de Buenos Aires a Madrid en business, cualquier día de julio 2027"
"""

from __future__ import annotations

import json
import sys

import anthropic
from anthropic import beta_tool

from buscar import cargar_env
from fuentes import seats_aero

MODELO = "claude-opus-5-5"

SISTEMA = """Sos un agente de viajes experto en canje de millas, especializado en Air Europa (UX, SkyTeam).
El usuario busca vuelos de Air Europa pagando con millas, por defecto en julio de 2027.

Cómo trabajar:
- Convertí ciudades a códigos IATA (Buenos Aires = EZE, Madrid = MAD, etc.). Si hay varios aeropuertos útiles, buscá con todos separados por coma.
- Usá `buscar_premios` para todo el rango de fechas de una vez; no consultes día por día.
- Si el usuario quiere ida y vuelta, hacé dos búsquedas (ida y regreso).
- Para las mejores 2-3 opciones, pedí `detalle_vuelos` y mostrá números de vuelo, horarios, escalas y tasas.
- Presentá una tabla corta ordenada por millas y explicá con qué programa conviene emitir.
- Aclarale que seats.aero es un caché: la disponibilidad se confirma en la web del programa antes de transferir millas.
- Recordale que con millas SUMA (programa propio de Air Europa) el precio es dinámico y se consulta en aireuropa.com
  (modo `python buscar.py capturar` / `repetir` de este proyecto); las búsquedas de seats.aero muestran el cupo de socios SkyTeam.
- No inventes disponibilidad ni precios: si una herramienta falla o no hay resultados, decilo.
Respondé en español rioplatense, claro y concreto."""


@beta_tool
def buscar_premios(
    origen: str,
    destino: str,
    fecha_desde: str = "2027-07-01",
    fecha_hasta: str = "2027-07-31",
    cabina: str = "economy",
    solo_directos: bool = False,
) -> str:
    """Busca asientos premio en vuelos operados por Air Europa (UX) en programas SkyTeam vía seats.aero.

    Args:
        origen: Código(s) IATA de origen, separados por coma, p. ej. "EZE" o "EZE,MVD".
        destino: Código(s) IATA de destino, separados por coma, p. ej. "MAD,BCN".
        fecha_desde: Primer día del rango, formato AAAA-MM-DD.
        fecha_hasta: Último día del rango, formato AAAA-MM-DD.
        cabina: Una de economy, premium, business, first.
        solo_directos: True para mostrar solo vuelos sin escalas.
    """
    if cabina not in seats_aero.CABINAS:
        return f"Cabina inválida: {cabina}. Opciones: {', '.join(seats_aero.CABINAS)}"
    try:
        filas = seats_aero.buscar(origen, destino, fecha_desde, fecha_hasta, cabina, solo_directos=solo_directos)
    except (seats_aero.SeatsAeroError, Exception) as e:  # el modelo tiene que ver el error para explicarlo
        return f"ERROR al consultar seats.aero: {e}"
    if not filas:
        return "Sin disponibilidad premio en vuelos de Air Europa para esos criterios."
    return json.dumps([f.to_dict() for f in filas[:60]], ensure_ascii=False)


@beta_tool
def detalle_vuelos(disponibilidad_id: str) -> str:
    """Devuelve los itinerarios concretos (vuelos, horarios, escalas, tasas) de un resultado de buscar_premios.

    Args:
        disponibilidad_id: El campo "id" de un resultado de buscar_premios.
    """
    try:
        return json.dumps(seats_aero.detalle_vuelos(disponibilidad_id), ensure_ascii=False)
    except Exception as e:
        return f"ERROR al pedir el detalle: {e}"


def responder(cliente: anthropic.Anthropic, historial: list) -> None:
    runner = cliente.beta.messages.tool_runner(
        model=MODELO,
        max_tokens=16000,
        system=SISTEMA,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        tools=[buscar_premios, detalle_vuelos],
        thread=False,  # mandamos el historial completo; lo llevamos nosotros entre turnos
        messages=list(historial),
    )
    for mensaje in runner:
        for bloque in mensaje.content:
            if bloque.type == "tool_use":
                print(f"  [buscando: {bloque.name} {json.dumps(bloque.input, ensure_ascii=False)}]")
        if mensaje.stop_reason == "refusal":
            print("El modelo no pudo responder esta consulta.")
        historial.append({"role": "assistant", "content": mensaje.content})
        if mensaje.stop_reason != "tool_use":
            print("\n" + "".join(b.text for b in mensaje.content if b.type == "text"))
        else:
            # el runner agrega los resultados de herramientas; los copiamos al historial propio
            resultados = runner.generate_tool_call_response()
            if resultados:
                historial.append(resultados)


def main() -> None:
    cargar_env()
    cliente = anthropic.Anthropic()
    historial: list = []
    primera = " ".join(sys.argv[1:])
    print("Agente de viajes Air Europa con millas. Escribí 'salir' para terminar.\n")
    while True:
        texto = primera or input("Vos: ").strip()
        primera = ""
        if texto.lower() in ("salir", "exit", "q"):
            break
        if not texto:
            continue
        historial.append({"role": "user", "content": texto})
        responder(cliente, historial)


if __name__ == "__main__":
    main()
