"""Ritmo de las partidas: variedad de aves, cuentas previas y pausas de resultado.

Estas pruebas no levantan servidor: fijan las constantes y el generador que
marcan cuánto espera el jugador entre una ronda y la siguiente.
"""
from __future__ import annotations

import apoyo  # noqa: F401  (deja la raíz del proyecto en sys.path)

from arbitro import cajas, clasico, minijuegos, nucleo


def probar_aves_varian_entre_rondas() -> None:
    for nivel in range(1, 6):
        cantidades = {len(clasico.generar_pajaros(nivel)) for _ in range(40)}
        assert len(cantidades) >= 3, f"nivel {nivel} repite siempre {cantidades}"
        assert 5 <= min(cantidades), cantidades
        assert max(cantidades) <= 18, cantidades
    print("Aves: la cantidad cambia dentro de cada nivel y sigue entre 5 y 18")


def probar_aves_no_repiten_la_cantidad_anterior() -> None:
    for _ in range(40):
        assert len(clasico.generar_pajaros(3, evitar=11)) != 11
    print("Aves: se evita repetir la cantidad de la ronda anterior")


def probar_cuentas_previas_son_rapidas() -> None:
    assert nucleo.TIEMPO_CUENTA_PREVIA == 0.8
    assert cajas.TIEMPO_CUENTA_CAJAS == 0.8
    assert minijuegos.TIEMPO_CUENTA_MINI == 0.8
    print("Cuentas previas: 0,8 s en clásicos, cajas y minijuegos")


def probar_resultados_no_frenan_la_partida() -> None:
    assert nucleo.TIEMPO_RESULTADO == 1.5
    print("Resultados: pausa de 1,5 s entre rondas")


def main() -> None:
    probar_aves_varian_entre_rondas()
    probar_aves_no_repiten_la_cantidad_anterior()
    probar_cuentas_previas_son_rapidas()
    probar_resultados_no_frenan_la_partida()
    print("OK - Ritmo")


if __name__ == "__main__":
    main()
