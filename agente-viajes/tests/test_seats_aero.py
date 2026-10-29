"""Prueba del parseo de seats.aero con respuestas simuladas (sin red)."""

import httpx

from fuentes import seats_aero


def _fila(id_, fecha, millas, aerolineas, disponible=True):
    return {
        "ID": id_,
        "Date": fecha,
        "Source": "flyingblue",
        "Route": {"OriginAirport": "EZE", "DestinationAirport": "MAD"},
        "JAvailable": disponible,
        "JMileageCost": millas,
        "JRemainingSeats": 2,
        "JAirlines": aerolineas,
        "JDirect": True,
        "UpdatedAt": "2026-10-28T10:00:00Z",
    }


def test_filtra_air_europa_pagina_y_ordena():
    paginas = [
        {"data": [_fila("a", "2027-07-05", "95000", "UX"), _fila("b", "2027-07-06", 70000, "AF")], "hasMore": True, "cursor": 1},
        {"data": [_fila("c", "2027-07-20", "72,500", "UX, AF"), _fila("d", "2027-07-21", 50000, "UX", False)], "hasMore": False},
    ]
    pedidos = []

    def manejar(req: httpx.Request) -> httpx.Response:
        pedidos.append(req)
        assert req.headers["Partner-Authorization"] == "k"
        return httpx.Response(200, json=paginas[len(pedidos) - 1])

    res = seats_aero.buscar("eze", "mad", "2027-07-01", "2027-07-31", "business", api_key="k", transport=httpx.MockTransport(manejar))

    assert [r.id for r in res] == ["c", "a"]  # sin AF-solo, sin no disponibles, ordenado por millas
    assert res[0].millas == 72500
    assert pedidos[0].url.params["origin_airport"] == "EZE"
    assert pedidos[0].url.params["cabins"] == "business"
    assert pedidos[1].url.params["cursor"] == "1"
