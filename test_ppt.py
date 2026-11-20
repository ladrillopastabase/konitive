"""Pruebas del generador de «Piedra · Papel · Tijera».

La consigna es invertida: ciertas rondas piden ganar contra la mano que muestra
el rival y el resto piden perder a propósito. La respuesta correcta es siempre
una mano distinta de la del rival.
"""
from __future__ import annotations

import asyncio

from juego.minijuegos import (
    JUEGOS_MINI, NOMBRES_MINI, RONDAS_MINI, generar, generar_ppt, mana_para,
)
from arbitro.nucleo import JUEGOS_FIESTA, NOMBRES_JUEGOS
from arbitro.minijuegos import (
    MINIJUEGOS_SOLO_PANTALLA, SECRETOS_MINI, TIEMPO_RESPUESTA_MINI,
    VISUAL_MINI, datos_para_resultado, estimulo_para_mando, visual_mini,
)


def probar_manos_ganan_y_pierden_contra_cada_rival():
    assert mana_para("piedra", "ganar") == "papel"
    assert mana_para("papel", "ganar") == "tijera"
    assert mana_para("tijera", "ganar") == "piedra"
    assert mana_para("piedra", "perder") == "tijera"
    assert mana_para("papel", "perder") == "piedra"
    assert mana_para("tijera", "perder") == "papel"


def probar_generar_ppt_cumple_la_consigna_y_nunca_empata():
    for ronda in range(1, 31):
        reto = generar_ppt(ronda)
        assert reto["rival"] in ("piedra", "papel", "tijera")
        assert reto["objetivo"] == ("ganar" if ronda % 3 == 1 else "perder")
        assert reto["esperado"] == mana_para(reto["rival"], reto["objetivo"])
        assert reto["esperado"] != reto["rival"]
        assert reto["ronda"] == ronda


def probar_generar_ppt_registrado():
    assert JUEGOS_MINI[-1] == "ppt"
    assert NOMBRES_MINI["ppt"] == "PIEDRA · PAPEL · TIJERA"
    assert RONDAS_MINI["ppt"] == 10
    assert generar(5, "ppt")["objetivo"] == generar_ppt(5)["objetivo"]


def probar_ppt_registrado_en_nucleo_y_arbitro():
    assert JUEGOS_FIESTA[-1] == "ppt"
    assert NOMBRES_JUEGOS["ppt"] == "PIEDRA · PAPEL · TIJERA"
    assert "ppt" in MINIJUEGOS_SOLO_PANTALLA
    assert SECRETOS_MINI["ppt"] == ("esperado",)
    assert VISUAL_MINI["ppt"] == ("rival", "objetivo")
    assert TIEMPO_RESPUESTA_MINI["ppt"] == 4.0


def probar_ppt_no_filtra_la_respuesta_en_el_estimulo():
    reto = generar_ppt(4)
    visual = visual_mini("ppt", reto)
    mando = estimulo_para_mando("ppt", reto)
    assert visual == {"rival": reto["rival"], "objetivo": reto["objetivo"]}
    assert mando == {"mira": True}
    for secreto in SECRETOS_MINI["ppt"]:
        assert secreto not in visual
        assert secreto not in mando


def probar_ppt_revela_respuesta_solo_en_el_resultado():
    reto = generar_ppt(5)
    datos = datos_para_resultado("ppt", reto)
    assert set(datos) == {"rival", "objetivo", "esperado"}
    assert datos["esperado"] == reto["esperado"]


async def main() -> None:
    probar_manos_ganan_y_pierden_contra_cada_rival()
    print("Manos: ganar y perder contra cada rival correctos")
    probar_generar_ppt_cumple_la_consigna_y_nunca_empata()
    print("Generador: consigna invertida y sin empates correcta")
    probar_generar_ppt_registrado()
    print("Registro: juego, nombre, rondas y despacho correctos")
    probar_ppt_registrado_en_nucleo_y_arbitro()
    print("Núcleo y árbitro: ppt registrado y su respuesta protegida")
    probar_ppt_no_filtra_la_respuesta_en_el_estimulo()
    print("Estímulo: pantalla ve rival y objetivo, mando solo mira")
    probar_ppt_revela_respuesta_solo_en_el_resultado()
    print("Resultado: la respuesta se revela solo al terminar la ronda")
    print("\nOK - Piedra papel tijera correcto")


if __name__ == "__main__":
    asyncio.run(main())
