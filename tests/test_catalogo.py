"""El catálogo es la única lista de juegos: servidor y cliente lo siguen.

Si añades un juego al catálogo y olvidas su bucle, su archivo de cliente o la
etiqueta <script>, esta prueba dice exactamente qué falta.
"""
from __future__ import annotations

from apoyo import RAIZ, cliente_js  # primero: deja la raíz del proyecto en sys.path

import json
import re

import servidor
from arbitro.nucleo import JUEGOS_FIESTA, NOMBRES_JUEGOS, leer_ajustes_fiesta
from arbitro.sesiones import BUCLES
from juego.catalogo import CATALOGO, IDS
from juego.minijuegos import JUEGOS_MINI, NOMBRES_MINI

# Juegos que comparten archivo de cliente en vez de tener uno propio.
ARCHIVO_CLIENTE = {"pajaros": "clasicos", "escritura": "clasicos"}


def probar_entradas_completas() -> None:
    assert len(IDS) == len(set(IDS)), "Hay ids repetidos en el catálogo"
    for juego in CATALOGO:
        assert set(juego) == {"id", "nombre", "descripcion", "dificultades"}, juego
        assert juego["nombre"].isupper(), juego["nombre"]
        assert "Conita" in juego["descripcion"], juego["id"]
        assert juego["dificultades"][0] == "facil", juego["id"]


def probar_servidor_deriva_todo_del_catalogo() -> None:
    assert JUEGOS_FIESTA == IDS
    assert NOMBRES_JUEGOS == {j["id"]: j["nombre"] for j in CATALOGO}
    assert set(BUCLES) == set(IDS), set(BUCLES) ^ set(IDS)
    assert set(JUEGOS_MINI) <= set(IDS)
    assert all(NOMBRES_MINI[j] == NOMBRES_JUEGOS[j] for j in JUEGOS_MINI)


def probar_cada_juego_tiene_cliente_cargado() -> None:
    html = (RAIZ / "static/index.html").read_text(encoding="utf-8")
    cargados = set(re.findall(r'<script src="/static/juegos/(\w+)\.js"', html))
    en_disco = {p.stem for p in (RAIZ / "static/juegos").glob("*.js")}
    assert cargados == en_disco, f"Sin <script> o sin archivo: {cargados ^ en_disco}"
    js = cliente_js()
    for juego in IDS:
        archivo = ARCHIVO_CLIENTE.get(juego, juego)
        assert archivo in cargados, f"{juego}: falta static/juegos/{archivo}.js"
        if juego in JUEGOS_MINI:
            assert f'registrarMini("{juego}"' in js, f"{juego} no llama a registrarMini"
    # El catálogo se carga antes que cualquier script del cliente.
    assert html.index('src="/api/catalogo.js"') < html.index('src="/static/nucleo.js"')


def probar_catalogo_js_es_valido() -> None:
    prefijo = "const CATALOGO = "
    assert servidor.CATALOGO_JS.startswith(prefijo)
    datos = json.loads(servidor.CATALOGO_JS[len(prefijo):].rstrip().rstrip(";"))
    assert [j["id"] for j in datos] == list(IDS)


def probar_dificultades_por_juego() -> None:
    _, ajustes = leer_ajustes_fiesta(
        ["rastreo", "cajas", "stroop"],
        {
            "rastreo": {"dificultad": "experto"},
            "cajas": {"dificultad": "experto"},
            "stroop": {"dificultad": ["lista"]},
        },
    )
    assert ajustes["rastreo"]["dificultad"] == "experto"
    assert ajustes["cajas"]["dificultad"] == "facil", "Solo RASTREO tiene experto"
    assert ajustes["stroop"]["dificultad"] == "facil"


def main() -> None:
    probar_entradas_completas()
    probar_servidor_deriva_todo_del_catalogo()
    probar_cada_juego_tiene_cliente_cargado()
    probar_catalogo_js_es_valido()
    probar_dificultades_por_juego()
    print("OK - Catálogo único: servidor, cliente e index.html coinciden")


if __name__ == "__main__":
    main()
