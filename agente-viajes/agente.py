"""Agente de viajes conversacional: busca vuelos de Air Europa canjeando millas.

Uso:
  python agente.py
  python agente.py "¿Qué fechas me convienen para ir y volver con mis millas?"
"""

from __future__ import annotations

import json
import sys

import anthropic
from anthropic import beta_tool

import config
from buscar import RESULTADOS, cargar_env, leer
from fuentes import seats_aero
from fuentes.combinar import combinar

MODELO = "claude-opus-5-5"

SISTEMA = f"""Sos un agente de viajes experto en canje de millas, especializado en Air Europa (UX, SkyTeam).

Perfil del viajero (de config.py):
- Saldo: {config.MILLAS_DISPONIBLES:,} millas {config.PROGRAMA} (programa propio de Air Europa).
- Ruta: {config.ORIGEN} (Córdoba, Argentina) -> {config.DESTINO} (Valencia, España), ida y vuelta.
- Ventana: salida desde {config.VENTANA_DESDE}, regreso a más tardar el {config.VENTANA_HASTA}.
- Air Europa vuela directo Córdoba-Madrid y conecta a Valencia en Madrid, todo con UX.

Cómo trabajar:
- La fuente principal son las búsquedas SUMA en aireuropa.com, que el usuario corre con
  `python buscar.py repetir --tramo ida` y `--tramo vuelta`. Leelas con `combinar_suma`.
  Si faltan, explicale los pasos (`capturar` y `repetir` para cada tramo) en vez de inventar datos.
- Priorizá combinaciones ida+vuelta que entren en el saldo; si ninguna entra, decí cuántas millas faltan
  y proponé alternativas: solo ida, mover fechas, salir desde Buenos Aires (EZE), o comprar millas en promo.
- `buscar_premios` (seats.aero) muestra cupo de socios SkyTeam (Flying Blue, Delta...): sirve como referencia,
  pero el usuario tiene millas SUMA, así que no lo presentes como canjeable con su saldo.
- Recordá que las tasas se pagan aparte en efectivo y que hay que confirmar en aireuropa.com antes de emitir.
- No inventes disponibilidad ni precios: si una herramienta falla o no hay resultados, decilo.
Presentá una tabla corta ordenada por millas. Respondé en español rioplatense, claro y concreto."""


@beta_tool
def combinar_suma(min_dias: int = 1, max_dias: int = 0) -> str:
    """Lee los resultados SUMA guardados (ida y vuelta) y devuelve las combinaciones que entran en el saldo.

    Args:
        min_dias: Estadía mínima en días.
        max_dias: Estadía máxima en días (0 = sin límite).
    """
    try:
        idas, vueltas = leer("suma_ida"), leer("suma_vuelta")
    except SystemExit as e:
        return f"Todavía no hay resultados SUMA en {RESULTADOS}: {e}"
    combos = combinar(idas, vueltas, config.MILLAS_DISPONIBLES, min_dias, max_dias or None)
    baratos = lambda filas: sorted(filas, key=lambda o: int(o["millas"]))[:10]
    return json.dumps(
        {"saldo": config.MILLAS_DISPONIBLES, "combinaciones": combos[:30], "idas_mas_baratas": baratos(idas), "vueltas_mas_baratas": baratos(vueltas)},
        ensure_ascii=False,
    )


@beta_tool
def buscar_premios(
    origen: str,
    destino: str,
    fecha_desde: str = config.VENTANA_DESDE,
    fecha_hasta: str = config.VENTANA_HASTA,
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
        tools=[combinar_suma, buscar_premios, detalle_vuelos],
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
    print(f"Agente de viajes Air Europa: {config.ORIGEN} -> {config.DESTINO} con {config.MILLAS_DISPONIBLES} millas {config.PROGRAMA}. Escribí 'salir' para terminar.\n")
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
