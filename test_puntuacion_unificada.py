"""Fórmula única de Brain Age para las 13 pruebas.

Parte de una función pura y crece con pruebas de integración por juego.
"""
from __future__ import annotations

import asyncio
import contextlib
import time

from arbitro import clasico
from arbitro.nucleo import Jugador, Sala
from arbitro.puntuacion import brain_age_y_puntos, fallos_escritura, sumar_historial


async def _sin_pausa(*_args, **_kwargs) -> None:
    """Las pausas reales (3 s + observación) no aportan a estas pruebas."""


def _sala_clasica(juego: str, historial: list[dict] | None = None) -> Sala:
    sala = Sala(codigo="TEST1", host_id="yo", modo="individual", capacidad=1)
    sala.jugadores["yo"] = Jugador(id="yo", nombre="YO", ws=None)
    sala.fase = juego
    sala.historial[juego] = historial or []
    return sala


@contextlib.contextmanager
def _con_pausas_desactivadas(esperar):
    """Sustituye solo las esperas lentas; el cálculo sigue siendo el real."""
    pausa_original = clasico.nucleo.pausa
    esperar_original = clasico.esperar
    clasico.nucleo.pausa = _sin_pausa
    clasico.esperar = esperar
    try:
        yield
    finally:
        clasico.nucleo.pausa = pausa_original
        clasico.esperar = esperar_original


def probar_formula_brain_age() -> None:
    assert brain_age_y_puntos(0.0, 0) == (0.0, 1000)
    assert brain_age_y_puntos(10.0, 0) == (10.0, 900)
    assert brain_age_y_puntos(10.0, 2) == (20.0, 800), "5 s por error"
    assert brain_age_y_puntos(2.0, 1) == (7.0, 930)
    assert brain_age_y_puntos(200.0, 0)[1] == 0, "los puntos no bajan de cero"


def probar_fallos_escritura() -> None:
    casillas = [
        {"estado": "aceptada", "intentos": 1, "motivo": "primera"},
        {"estado": "aceptada", "intentos": 2, "motivo": "posterior"},
        {"estado": "aceptada", "intentos": 3, "motivo": "automatica"},
    ]
    assert fallos_escritura(casillas) == 4, "0 + 1 + 3 rechazos"
    assert fallos_escritura(casillas, incompleto=True) == 5
    assert fallos_escritura([{"estado": "pendiente", "intentos": 2}]) == 2
    assert brain_age_y_puntos(4.0, 4) == (24.0, 760), "5 s por error"


def probar_sumar_historial() -> None:
    historial = [
        {
            "tiempo": {"yo": 2.0, "otro": 4.0},
            "errores": {"yo": 1, "otro": 0},
            "puntos": {"yo": 0, "otro": 0},
        }
    ]
    assert sumar_historial(historial, "yo", 3.0, 0) == (10.0, 900), historial
    assert sumar_historial(historial, "otro", 1.0, 1) == (10.0, 900), historial
    assert sumar_historial([], "yo", 0.5, 0) == (0.5, 995)


async def _esperar_respuesta_pajaros(sala, _evento, _segundos, instante) -> None:
    sala.respuestas["yo"] = (sala.datos["esperado"], instante)


async def _esperar_sin_respuesta_pajaros(sala, _evento, _segundos) -> None:
    return None


async def probar_ronda_pajaros_usa_tiempo_y_errores() -> None:
    sala = _sala_clasica("pajaros")
    async def esperar_correcta(sala_, evento, segundos):
        await _esperar_respuesta_pajaros(sala_, evento, segundos, sala_.datos["momento_respuesta"] + 2.0)
    with _con_pausas_desactivadas(esperar_correcta):
        puntos = await clasico.ronda_pajaros(sala, 1)
    assert puntos["yo"] == 980, (puntos, sala.datos)
    assert sala.datos["tiempo"]["yo"] == 2.0
    assert sala.datos["errores"]["yo"] == 0
    assert sala.datos["brain_age"]["yo"] == 2.0
    assert sala.datos["desglose"]["yo"]["total"] == 980

    sala = _sala_clasica("pajaros")
    async def esperar_mal(sala_, evento, segundos):
        await _esperar_respuesta_pajaros(sala_, evento, segundos, sala_.datos["momento_respuesta"] + 2.0)
        sala_.respuestas["yo"] = (sala_.datos["esperado"] + 1, sala_.datos["momento_respuesta"] + 2.0)
    with _con_pausas_desactivadas(esperar_mal):
        puntos = await clasico.ronda_pajaros(sala, 1)
    assert puntos["yo"] == 930, puntos
    assert sala.datos["errores"]["yo"] == 1
    assert sala.datos["brain_age"]["yo"] == 7.0


async def probar_ronda_pajaros_sin_respuesta_cuenta_error() -> None:
    sala = _sala_clasica("pajaros")
    with _con_pausas_desactivadas(_esperar_sin_respuesta_pajaros):
        puntos = await clasico.ronda_pajaros(sala, 1)
    esperado = brain_age_y_puntos(clasico.TIEMPO_ESPERA_RESPUESTA, 1)[1]
    assert puntos["yo"] == esperado, (puntos, esperado)
    assert sala.datos["tiempo"]["yo"] == clasico.TIEMPO_ESPERA_RESPUESTA
    assert sala.datos["errores"]["yo"] == 1


async def probar_ronda_pajaros_acumula_entre_rondas() -> None:
    historial = [{
        "tiempo": {"yo": 2.0}, "errores": {"yo": 0}, "puntos": {"yo": 980},
    }]
    sala = _sala_clasica("pajaros", historial=historial)
    async def esperar_correcta(sala_, evento, segundos):
        await _esperar_respuesta_pajaros(sala_, evento, segundos, sala_.datos["momento_respuesta"] + 3.0)
    with _con_pausas_desactivadas(esperar_correcta):
        puntos = await clasico.ronda_pajaros(sala, 1)
    assert puntos["yo"] == brain_age_y_puntos(5.0, 0)[1], (puntos, sala.datos)
    assert sala.datos["brain_age"]["yo"] == 5.0


def _progreso_palabra(jugador, fin, intentos_por_letra: list[int] | None = None) -> None:
    letras = jugador.progreso["letras"]
    intentos = intentos_por_letra or [1] * len(letras)
    for i, (estado, n) in enumerate(zip(letras, intentos)):
        estado["estado"] = "aceptada"
        estado["intentos"] = n
        if n >= 3:
            estado["motivo"] = "automatica"
        else:
            estado["motivo"] = "correcta" if n == 1 else "posterior"
    jugador.progreso["fin"] = fin


async def probar_ronda_escritura_suma_intentos_fallidos() -> None:
    sala = _sala_clasica("escritura")
    async def esperar_escritura(sala_, evento, segundos):
        jugador = sala_.jugadores["yo"]
        _progreso_palabra(jugador, jugador.progreso["inicio"] + 4.0, [1, 2, 3])
    with _con_pausas_desactivadas(esperar_escritura):
        puntos = await clasico.ronda_escritura(sala, 1)
    # 0 rechazos + 1 rechazo + 3 rechazos (aceptación automática) = 4 errores
    assert puntos["yo"] == brain_age_y_puntos(4.0, 4)[1], (puntos, sala.datos["desglose"])
    desglose = sala.datos["desglose"]["yo"]
    assert desglose["errores"] == 4 and desglose["tiempo"] == 4.0


async def probar_ronda_escritura_sin_respuesta() -> None:
    sala = _sala_clasica("escritura")
    async def esperar_nada(_sala, _evento, _segundos):
        return None
    with _con_pausas_desactivadas(esperar_nada):
        puntos = await clasico.ronda_escritura(sala, 1)
    esperado = brain_age_y_puntos(clasico.TIEMPO_ESPERA_ESCRITURA, 1)[1]
    assert puntos["yo"] == esperado, (puntos, esperado)


def probar_resumen_clasico_no_suma_puntos_acumulados() -> None:
    """El informe final usa el Brain Age acumulado, no la suma de parciales."""
    historial = [
        {"tiempo": {"yo": 2.0}, "errores": {"yo": 0}, "puntos": {"yo": 980}},
        {"tiempo": {"yo": 4.0}, "errores": {"yo": 0}, "puntos": {"yo": 960}},
        {"tiempo": {"yo": 6.0}, "errores": {"yo": 0}, "puntos": {"yo": 940}},
    ]
    sala = _sala_clasica("pajaros", historial=historial)
    sala.rondas_juego["pajaros"] = 3
    sala.ganadas["pajaros"]["yo"] = 3
    resumen = clasico.resumen_clasico_individual(sala, "pajaros")
    assert resumen["tiempo_total"] == 12.0, resumen
    assert resumen["brain_age"] == 12.0, resumen
    assert resumen["puntos"] == 880 and resumen["total"] == 880, resumen
    assert resumen["mejor"] == 980, resumen


async def probar_escritura_sin_respuesta_no_cuenta_letras_correctas() -> None:
    """Una palabra sin responder no se informa como acertada al mando."""
    sala = _sala_clasica("escritura")

    async def esperar_nada(_sala, _evento, _segundos):
        return None

    with _con_pausas_desactivadas(esperar_nada):
        await clasico.ronda_escritura(sala, 1)
    desglose = sala.datos["desglose"]["yo"]
    assert desglose["correctas"] == 0, desglose
    assert desglose["automaticas"] == 0, desglose


class _WsFalso:
    def __init__(self) -> None:
        self.enviados: list[dict] = []

    async def send_json(self, mensaje: dict) -> None:
        self.enviados.append(mensaje)


async def probar_difusion_fiesta_oculta_metricas_de_desglose() -> None:
    """El tiempo, errores y Brain Age del primero no se filtran a los mandos."""
    sala = Sala(codigo="FIEST", host_id="pantalla", modo="fiesta", capacidad=2)
    ws_pantalla, ws_mando = _WsFalso(), _WsFalso()
    sala.jugadores["pantalla"] = Jugador(
        id="pantalla", nombre="PANTALLA", ws=ws_pantalla, rol="pantalla"
    )
    sala.jugadores["mando"] = Jugador(
        id="mando", nombre="MANDO", ws=ws_mando, rol="mando"
    )
    await sala.difundir(
        {
            "type": "cajas_over",
            "puntos": 495,
            "tiempo_total": 12.0,
            "errores": 2,
            "brain_age": 22.0,
        }
    )
    assert len(ws_pantalla.enviados) == 1, ws_pantalla.enviados
    assert {"tiempo_total", "errores", "brain_age"} <= ws_pantalla.enviados[0].keys()
    assert len(ws_mando.enviados) == 1, ws_mando.enviados
    assert not {"tiempo_total", "errores", "brain_age"} & ws_mando.enviados[0].keys()


def main() -> None:
    probar_formula_brain_age()
    probar_fallos_escritura()
    probar_sumar_historial()
    asyncio.run(probar_ronda_pajaros_usa_tiempo_y_errores())
    asyncio.run(probar_ronda_pajaros_sin_respuesta_cuenta_error())
    asyncio.run(probar_ronda_pajaros_acumula_entre_rondas())
    asyncio.run(probar_ronda_escritura_suma_intentos_fallidos())
    asyncio.run(probar_ronda_escritura_sin_respuesta())
    probar_resumen_clasico_no_suma_puntos_acumulados()
    asyncio.run(probar_escritura_sin_respuesta_no_cuenta_letras_correctas())
    asyncio.run(probar_difusion_fiesta_oculta_metricas_de_desglose())
    print("OK - Fórmula Brain Age compartida y clásicos")


if __name__ == "__main__":
    main()
