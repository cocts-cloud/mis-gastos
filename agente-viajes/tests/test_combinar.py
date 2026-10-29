from fuentes.combinar import combinar


def test_respeta_saldo_orden_y_fechas():
    idas = [{"fecha": "2027-06-25", "millas": 32000}, {"fecha": "2027-06-25", "millas": 45000}, {"fecha": "2027-07-01", "millas": 40000}]
    vueltas = [{"fecha": "2027-06-24", "millas": 32000}, {"fecha": "2027-07-18", "millas": 32000}, {"fecha": "2027-07-19", "millas": 38200}]
    res = combinar(idas, vueltas, 70_100, min_dias=7)
    # 06-25 + 07-19 = 70.200 y 07-01 + 07-18 = 72.000 superan el saldo; la vuelta del 24/06 es anterior a la ida
    assert [(c["ida"], c["vuelta"], c["total"]) for c in res] == [("2027-06-25", "2027-07-18", 64000)]
    assert res[0]["sobran"] == 6100
