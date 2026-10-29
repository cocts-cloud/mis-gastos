# Agente de viajes: Air Europa con millas (julio 2027)

## Tu viaje (config.py)

**Córdoba (COR) → Valencia (VLC), ida y vuelta, entre el 22/06 y el 20/07/2027, con 70.100 millas SUMA.**
Air Europa vuela directo Córdoba–Madrid y conecta con Valencia, así que todo el viaje se emite con SUMA.

```bash
python buscar.py capturar --tramo ida      # en el navegador: SUMA, COR → VLC, solo ida, "pagar con millas"
python buscar.py capturar --tramo vuelta   # VLC → COR, solo ida, "pagar con millas"
python buscar.py repetir --tramo ida       # recorre del 22/06 al 20/07
python buscar.py repetir --tramo vuelta
python buscar.py combinar --min-dias 10    # pares ida+vuelta que entran en 70.100 millas
python agente.py "¿Qué combinación me conviene?"
```

Referencia (no oficial, 2026): la tarifa "Turista SUMA" Argentina–España sale unas **32.000 millas por tramo**
más tasas en efectivo, así que ida y vuelta en turista (~64.000) entra en tu saldo si hay cupo esas fechas.
Business ronda las 64.000 millas **por tramo**: alcanza solo para una ida.

Agente que busca vuelos **operados por Air Europa (UX)** que se pueden pagar con millas, por defecto para
todo **julio de 2027**. Tiene dos fuentes de datos, porque Air Europa **no tiene una API pública** de canjes:

| Fuente | Qué ve | Cómo se conecta | Estabilidad |
|---|---|---|---|
| **seats.aero** (`fuentes/seats_aero.py`) | Cupo premio de UX que publican los socios SkyTeam: Flying Blue, Delta SkyMiles, Aeroméxico Club Premier, Virgin Atlantic | API oficial de partners (requiere [seats.aero Pro](https://seats.aero), unos USD 10/mes) | Alta |
| **aireuropa.com / SUMA** (`fuentes/air_europa_web.py`) | Precio en millas SUMA (el programa propio de Air Europa), que es dinámico | Navegador real (Playwright) con tu sesión | Experimental: la web cambia y tiene anti-bots |

> ¿Qué millas tenés? Si son **SUMA**, la fuente que cuenta es aireuropa.com. Si son **Flying Blue / Delta /
> Aeroméxico** (o las transferís desde una tarjeta), seats.aero es lo más rápido y confiable.

## Instalación

```bash
cd agente-viajes
pip install -r requirements.txt
playwright install chromium   # solo si vas a usar el modo SUMA
cp .env.example .env          # y completá ANTHROPIC_API_KEY y SEATS_AERO_API_KEY
```

## 1. Agente conversacional (Claude)

```bash
python agente.py "Ida y vuelta Buenos Aires–Madrid en business, salgo la primera quincena de julio 2027 y vuelvo la segunda"
```

El agente traduce ciudades a aeropuertos, busca todo el rango de fechas, pide el detalle de los mejores vuelos
(horarios, escalas, tasas) y te dice con qué programa conviene emitir. Usa `claude-opus-5-5` con *fallback*
automático del lado del servidor si el modelo rechaza una consulta.

## 2. Búsqueda directa, sin IA

```bash
# Socios SkyTeam vía seats.aero (genera un CSV en resultados/)
python buscar.py seats --origen EZE --destino MAD,BCN --desde 2027-07-01 --hasta 2027-07-31 --cabina business

# Millas SUMA en aireuropa.com
python buscar.py capturar   # abre Chrome: iniciás sesión en SUMA y hacés UNA búsqueda "pagar con millas"
python buscar.py repetir --desde 2027-07-01 --hasta 2027-07-31   # repite esa búsqueda día por día
```

`capturar` guarda en `capturas/` todas las respuestas JSON de la búsqueda; `repetir` reutiliza esa misma
petición con tus cookies cambiando solo la fecha, con una pausa entre consultas (`--pausa`, 6 s por defecto).
Si Air Europa cambia su web y `repetir` no encuentra millas, mirá los JSON de `capturas/` y ajustá
`PALABRAS_BUSQUEDA` / `_extraer_ofertas` en `fuentes/air_europa_web.py`.

## Cosas a tener en cuenta

- **Fechas**: las aerolíneas abren la venta unos 330–360 días antes. Hoy (oct-2026) julio 2027 ya está o está por
  abrirse; si no ves resultados de la segunda mitad de julio, probá de nuevo en unas semanas.
- **seats.aero es un caché**: confirmá en la web del programa antes de transferir millas (las transferencias no se
  pueden deshacer).
- **Tasas**: Flying Blue cobra tasas y recargos que varían mucho por origen; `detalle_vuelos` las muestra.
- **Términos de uso**: el modo SUMA usa tu propia cuenta y consultas espaciadas. No lo uses para consultas masivas.

## Tests

```bash
python -m pytest -q tests
```
