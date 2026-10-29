"""Modo navegador contra aireuropa.com (programa SUMA). EXPERIMENTAL.

Air Europa no ofrece una API pública para canjear millas SUMA. Este módulo
usa un navegador real (Playwright) en dos pasos:

1. `capturar`: abre Chromium con un perfil propio. Vos iniciás sesión en SUMA
   y hacés UNA búsqueda solo ida "pagar con millas" (una para la ida y
   otra para la vuelta). El script guarda todas las
   respuestas JSON que la web recibe (en capturas/) y la petición de búsqueda.
2. `repetir`: reutiliza esa petición con tus cookies, cambiando la fecha día
   por día (toda tu ventana de viaje), y extrae los precios en millas.

La web de Air Europa cambia seguido y tiene protección anti-bots: si algo
falla, revisá las capturas y ajustá PALABRAS_BUSQUEDA / _extraer_ofertas.
Usalo para tu cuenta, con pausas entre consultas, y respetando los términos
del sitio.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PERFIL = RAIZ / "perfil-navegador"
CAPTURAS = RAIZ / "capturas"


def _peticion(nombre: str) -> Path:
    return CAPTURAS / f"peticion_{nombre}.json"


URL_INICIO = "https://www.aireuropa.com/"
# Fragmentos de URL que suelen tener las llamadas de búsqueda de vuelos.
PALABRAS_BUSQUEDA = ("availability", "search", "flights", "offers", "calendar", "fares")
RE_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")
RE_FECHA_COMPACTA = re.compile(r"(?<!\d)20\d{2}[01]\d[0-3]\d(?!\d)")


def _es_busqueda(url: str) -> bool:
    u = url.lower()
    return "aireuropa" in u and any(p in u for p in PALABRAS_BUSQUEDA)


def capturar(nombre: str = "ida") -> None:
    """Guarda la búsqueda que hagas a mano en el navegador bajo `nombre` (ida / vuelta)."""
    from playwright.sync_api import sync_playwright

    CAPTURAS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PERFIL), headless=False, locale="es-ES")
        pagina = ctx.pages[0] if ctx.pages else ctx.new_page()
        n = 0

        def al_responder(resp):
            nonlocal n
            if "json" not in (resp.headers.get("content-type") or ""):
                return
            if not _es_busqueda(resp.url):
                return
            try:
                cuerpo = resp.json()
            except Exception:
                return
            n += 1
            (CAPTURAS / f"{nombre}_respuesta_{n:03d}.json").write_text(
                json.dumps({"url": resp.url, "cuerpo": cuerpo}, ensure_ascii=False, indent=2)
            )
            req = resp.request
            if RE_FECHA.search((req.post_data or "") + req.url) or RE_FECHA_COMPACTA.search((req.post_data or "") + req.url):
                _peticion(nombre).write_text(
                    json.dumps(
                        {"metodo": req.method, "url": req.url, "headers": req.headers, "cuerpo": req.post_data},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            print(f"  capturada: {resp.url[:110]}")

        pagina.on("response", al_responder)
        pagina.goto(URL_INICIO)
        print(
            f"\n1) Iniciá sesión en SUMA.\n2) Buscá un vuelo SOLO IDA ({nombre}) marcando 'Pagar con millas'.\n"
            "3) Cuando veas los resultados, volvé acá y apretá Enter.\n"
        )
        input()
        ctx.close()
    print(f"Listo: {n} respuestas en {CAPTURAS}. Petición de búsqueda '{nombre}': {'sí' if _peticion(nombre).exists() else 'no encontrada'}")


def _extraer_ofertas(nodo, fecha: str, salida: list[dict]) -> None:
    """Recorre el JSON buscando objetos con un precio en millas/puntos."""
    if isinstance(nodo, dict):
        claves = {k.lower(): k for k in nodo}
        clave_millas = next((claves[k] for k in claves if any(w in k for w in ("miles", "millas", "points", "avios"))), None)
        if clave_millas is not None and isinstance(nodo[clave_millas], (int, float, str)):
            millas = re.sub(r"[^\d]", "", str(nodo[clave_millas]))
            if millas:
                salida.append(
                    {
                        "fecha": fecha,
                        "millas": int(millas),
                        "vuelo": next((str(nodo[claves[k]]) for k in claves if "flightnumber" in k or k == "flight"), ""),
                        "cabina": next((str(nodo[claves[k]]) for k in claves if "cabin" in k or "class" in k), ""),
                        "tasas": next((nodo[claves[k]] for k in claves if "tax" in k), None),
                    }
                )
        for v in nodo.values():
            _extraer_ofertas(v, fecha, salida)
    elif isinstance(nodo, list):
        for v in nodo:
            _extraer_ofertas(v, fecha, salida)


def _reemplazar_fecha(texto: str, original: str, nueva: date) -> str:
    if "-" in original:
        return texto.replace(original, nueva.isoformat())
    return texto.replace(original, nueva.strftime("%Y%m%d"))


def repetir(fecha_desde: str, fecha_hasta: str, pausa_seg: float = 6.0, nombre: str = "ida") -> list[dict]:
    """Repite la búsqueda capturada `nombre` para cada día del rango usando tu sesión."""
    from playwright.sync_api import sync_playwright

    if not _peticion(nombre).exists():
        raise RuntimeError(f"Primero corré: python buscar.py capturar --tramo {nombre}")
    plantilla = json.loads(_peticion(nombre).read_text())
    texto = (plantilla["cuerpo"] or "") + plantilla["url"]
    encontrada = RE_FECHA.search(texto) or RE_FECHA_COMPACTA.search(texto)
    fecha_original = encontrada.group(0)
    headers = {k: v for k, v in plantilla["headers"].items() if not k.startswith(":") and k.lower() not in ("content-length", "cookie")}

    d, fin = date.fromisoformat(fecha_desde), date.fromisoformat(fecha_hasta)
    ofertas: list[dict] = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PERFIL), headless=False, locale="es-ES")
        pagina = ctx.pages[0] if ctx.pages else ctx.new_page()
        pagina.goto(URL_INICIO)  # refresca cookies anti-bot
        while d <= fin:
            f = d.isoformat()
            resp = ctx.request.fetch(
                _reemplazar_fecha(plantilla["url"], fecha_original, d),
                method=plantilla["metodo"],
                headers=headers,
                data=_reemplazar_fecha(plantilla["cuerpo"] or "", fecha_original, d) or None,
            )
            if resp.ok:
                try:
                    _extraer_ofertas(resp.json(), f, ofertas)
                except Exception:
                    print(f"  {f}: respuesta no JSON (¿sesión vencida o bloqueo anti-bot?)")
            else:
                print(f"  {f}: HTTP {resp.status}")
            d += timedelta(days=1)
            time.sleep(pausa_seg)
        ctx.close()
    ofertas.sort(key=lambda o: (o["millas"], o["fecha"]))
    return ofertas
