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


async def main() -> None:
    probar_manos_ganan_y_pierden_contra_cada_rival()
    print("Manos: ganar y perder contra cada rival correctos")
    probar_generar_ppt_cumple_la_consigna_y_nunca_empata()
    print("Generador: consigna invertida y sin empates correcta")
    probar_generar_ppt_registrado()
    print("Registro: juego, nombre, rondas y despacho correctos")
    print("\nOK - Piedra papel tijera correcto")


if __name__ == "__main__":
    asyncio.run(main())
