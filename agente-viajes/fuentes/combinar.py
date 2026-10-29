"""Arma combinaciones ida + vuelta que entren en el saldo de millas."""

from __future__ import annotations

from datetime import date


def _mejor_por_dia(ofertas: list[dict]) -> dict[str, dict]:
    mejor: dict[str, dict] = {}
    for o in ofertas:
        if o["fecha"] not in mejor or int(o["millas"]) < int(mejor[o["fecha"]]["millas"]):
            mejor[o["fecha"]] = o
    return mejor


def combinar(
    idas: list[dict],
    vueltas: list[dict],
    millas_disponibles: int,
    min_dias: int = 1,
    max_dias: int | None = None,
) -> list[dict]:
    """Devuelve pares ida/vuelta con vuelta posterior a la ida y total <= saldo, de menor a mayor."""
    combos = []
    for fi, ida in _mejor_por_dia(idas).items():
        for fv, vuelta in _mejor_por_dia(vueltas).items():
            dias = (date.fromisoformat(fv) - date.fromisoformat(fi)).days
            if dias < min_dias or (max_dias is not None and dias > max_dias):
                continue
            total = int(ida["millas"]) + int(vuelta["millas"])
            if total > millas_disponibles:
                continue
            combos.append(
                {
                    "ida": fi,
                    "vuelta": fv,
                    "dias": dias,
                    "millas_ida": int(ida["millas"]),
                    "millas_vuelta": int(vuelta["millas"]),
                    "total": total,
                    "sobran": millas_disponibles - total,
                    "vuelos_ida": ida.get("vuelo", ""),
                    "vuelos_vuelta": vuelta.get("vuelo", ""),
                }
            )
    combos.sort(key=lambda c: (c["total"], -c["dias"]))
    return combos
