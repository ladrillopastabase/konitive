"""Fórmula única de puntuación para las 13 pruebas.

Parte de una función pura y crece con pruebas de integración por juego.
"""
from __future__ import annotations

import apoyo  # primero: deja la raíz del proyecto en sys.path

import asyncio
import contextlib
import time

from arbitro import clasico, nucleo
from arbitro.nucleo import Jugador, Sala, decidir_ganador
from arbitro.puntuacion import puntuacion, fallos_escritura, sumar_puntuacion


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


def probar_formula_solo_tiempo() -> None:
    """El resultado es segundos: tiempo + 5 s por error, sin escala invertida."""
    from arbitro import puntuacion

    assert hasattr(puntuacion, "puntuacion"), "falta la función puntuacion"
    assert puntuacion.puntuacion(7.0, 3) == 22.0
    assert puntuacion.puntuacion(12.0, 0) == 12.0
    assert puntuacion.sumar_puntuacion(
        [{"pid": "yo", "tiempo": 2.0, "errores": 1}], "yo", 3.0, 0
    ) == 10.0
    assert not hasattr(puntuacion, "PUNTOS_POR_SEGUNDO")


def probar_empate_puntuacion_no_tiene_ganador() -> None:
    """Dos tiempos iguales no deben dar un ganador arbitrario."""
    assert decidir_ganador({"a": 12.0, "b": 12.0}) is None
    assert decidir_ganador({"a": 12.0, "b": 17.0}) == "a"


def probar_formula_puntuacion() -> None:
    assert puntuacion(0.0, 0) == 0.0
    assert puntuacion(10.0, 0) == 10.0
    assert puntuacion(10.0, 2) == 20.0, "5 s por error"
    assert puntuacion(2.0, 1) == 7.0


def probar_fallos_escritura() -> None:
    casillas = [
        {"estado": "aceptada", "intentos": 1, "motivo": "primera"},
        {"estado": "aceptada", "intentos": 2, "motivo": "posterior"},
        {"estado": "aceptada", "intentos": 3, "motivo": "automatica"},
    ]
    assert fallos_escritura(casillas) == 4, "0 + 1 + 3 rechazos"
    assert fallos_escritura(casillas, incompleto=True) == 5
    assert fallos_escritura([{"estado": "pendiente", "intentos": 2}]) == 2
    assert puntuacion(4.0, 4) == 24.0, "5 s por error"


def probar_sumar_puntuacion() -> None:
    historial = [
        {
            "tiempo": {"yo": 2.0, "otro": 4.0},
            "errores": {"yo": 1, "otro": 0},
        }
    ]
    assert sumar_puntuacion(historial, "yo", 3.0, 0) == 10.0, historial
    assert sumar_puntuacion(historial, "otro", 1.0, 1) == 10.0, historial
    assert sumar_puntuacion([], "yo", 0.5, 0) == 0.5


async def _esperar_respuesta_pajaros(sala, _evento, _segundos, instante) -> None:
    sala.respuestas["yo"] = (sala.datos["esperado"], instante)


async def _esperar_sin_respuesta_pajaros(sala, _evento, _segundos) -> None:
    return None


async def probar_ronda_pajaros_usa_tiempo_y_errores() -> None:
    sala = _sala_clasica("pajaros")
    async def esperar_correcta(sala_, evento, segundos):
        await _esperar_respuesta_pajaros(sala_, evento, segundos, sala_.datos["momento_respuesta"] + 2.0)
    with _con_pausas_desactivadas(esperar_correcta):
        tiempos = await clasico.ronda_pajaros(sala, 1)
    assert tiempos["yo"] == 2.0, (tiempos, sala.datos)
    assert sala.datos["tiempo"]["yo"] == 2.0
    assert sala.datos["errores"]["yo"] == 0
    assert sala.datos["puntuacion"]["yo"] == 2.0
    assert sala.datos["desglose"]["yo"]["puntuacion"] == 2.0
    assert "total" not in sala.datos["desglose"]["yo"]

    sala = _sala_clasica("pajaros")
    async def esperar_mal(sala_, evento, segundos):
        await _esperar_respuesta_pajaros(sala_, evento, segundos, sala_.datos["momento_respuesta"] + 2.0)
        sala_.respuestas["yo"] = (sala_.datos["esperado"] + 1, sala_.datos["momento_respuesta"] + 2.0)
    with _con_pausas_desactivadas(esperar_mal):
        tiempos = await clasico.ronda_pajaros(sala, 1)
    assert tiempos["yo"] == 7.0, tiempos
    assert sala.datos["errores"]["yo"] == 1
    assert sala.datos["puntuacion"]["yo"] == 7.0


async def probar_ronda_pajaros_sin_respuesta_cuenta_error() -> None:
    sala = _sala_clasica("pajaros")
    with _con_pausas_desactivadas(_esperar_sin_respuesta_pajaros):
        tiempos = await clasico.ronda_pajaros(sala, 1)
    esperado = puntuacion(clasico.TIEMPO_ESPERA_RESPUESTA, 1)
    assert tiempos["yo"] == esperado, (tiempos, esperado)
    assert sala.datos["tiempo"]["yo"] == clasico.TIEMPO_ESPERA_RESPUESTA
    assert sala.datos["errores"]["yo"] == 1


async def probar_ronda_pajaros_acumula_entre_rondas() -> None:
    historial = [{
        "tiempo": {"yo": 2.0}, "errores": {"yo": 0}, "puntuacion": {"yo": 2.0},
    }]
    sala = _sala_clasica("pajaros", historial=historial)
    async def esperar_correcta(sala_, evento, segundos):
        await _esperar_respuesta_pajaros(sala_, evento, segundos, sala_.datos["momento_respuesta"] + 3.0)
    with _con_pausas_desactivadas(esperar_correcta):
        tiempos = await clasico.ronda_pajaros(sala, 1)
    assert tiempos["yo"] == puntuacion(5.0, 0) == 5.0, (tiempos, sala.datos)
    assert sala.datos["puntuacion"]["yo"] == 5.0


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
        tiempos = await clasico.ronda_escritura(sala, 1)
    # 0 rechazos + 1 rechazo + 3 rechazos (aceptación automática) = 4 errores
    assert tiempos["yo"] == puntuacion(4.0, 4) == 24.0, (tiempos, sala.datos["desglose"])
    desglose = sala.datos["desglose"]["yo"]
    assert desglose["errores"] == 4 and desglose["tiempo"] == 4.0


async def probar_ronda_escritura_sin_respuesta() -> None:
    sala = _sala_clasica("escritura")
    async def esperar_nada(_sala, _evento, _segundos):
        return None
    with _con_pausas_desactivadas(esperar_nada):
        tiempos = await clasico.ronda_escritura(sala, 1)
    esperado = puntuacion(clasico.TIEMPO_ESPERA_ESCRITURA, 1)
    assert tiempos["yo"] == esperado, (tiempos, esperado)


def probar_resumen_clasico_no_suma_puntos_acumulados() -> None:
    """El informe final usa la puntuación acumulada, no la suma de parciales."""
    historial = [
        {"tiempo": {"yo": 2.0}, "errores": {"yo": 0}, "puntuacion": {"yo": 2.0}},
        {"tiempo": {"yo": 4.0}, "errores": {"yo": 0}, "puntuacion": {"yo": 4.0}},
        {"tiempo": {"yo": 6.0}, "errores": {"yo": 0}, "puntuacion": {"yo": 6.0}},
    ]
    sala = _sala_clasica("pajaros", historial=historial)
    sala.rondas_juego["pajaros"] = 3
    sala.ganadas["pajaros"]["yo"] = 3
    resumen = clasico.resumen_clasico_individual(sala, "pajaros")
    assert resumen["tiempo_total"] == 12.0, resumen
    assert resumen["puntuacion"] == 12.0, resumen
    assert resumen["mejor"] == 2.0, resumen
    assert "puntos" not in resumen and "total" not in resumen, resumen


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
    """El tiempo, errores y puntuación del primero no se filtran a los mandos."""
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
            "tiempo_total": 12.0,
            "errores": 2,
            "puntuacion": 22.0,
        }
    )
    assert len(ws_pantalla.enviados) == 1, ws_pantalla.enviados
    assert {"tiempo_total", "errores", "puntuacion"} <= ws_pantalla.enviados[0].keys()
    assert len(ws_mando.enviados) == 1, ws_mando.enviados
    assert not {"tiempo_total", "errores", "puntuacion"} & ws_mando.enviados[0].keys()


def probar_sin_api_antigua_de_puntos() -> None:
    """No queda la inversión 0–1000 ni ningún alias del contrato viejo."""
    from arbitro import puntuacion

    for nombre in (
        "puntuacion_y_puntos",
        "sumar_historial",
        "PUNTOS_BASE",
        "PUNTOS_POR_SEGUNDO",
    ):
        assert not hasattr(puntuacion, nombre), nombre


def _sin_clave_puntos(valor, ruta: str) -> None:
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            assert clave != "puntos", (ruta, clave)
            _sin_clave_puntos(hijo, f"{ruta}.{clave}")
    elif isinstance(valor, (list, tuple)):
        for indice, hijo in enumerate(valor):
            _sin_clave_puntos(hijo, f"{ruta}[{indice}]")


async def probar_mensajes_finales_sin_puntos() -> None:
    """Ningún informe final arrastra la clave de puntos de la escala vieja."""
    sala = _sala_clasica("pajaros")
    ws = _WsFalso()
    sala.jugadores["yo"].ws = ws
    await clasico.terminar_partida(sala, "yo")
    assert len(ws.enviados) == 1, ws.enviados
    _sin_clave_puntos(ws.enviados[0], "match_over")

    sala = Sala(codigo="FIEST", host_id="pantalla", modo="fiesta", capacidad=2)
    ws_pantalla, ws_mando = _WsFalso(), _WsFalso()
    sala.jugadores["pantalla"] = Jugador(
        id="pantalla", nombre="PANTALLA", ws=ws_pantalla, rol="pantalla"
    )
    sala.jugadores["mando"] = Jugador(
        id="mando", nombre="MANDO", ws=ws_mando, rol="mando"
    )
    sala.juego_fiesta = "pajaros"
    sala.ultimas_puntuaciones = {"mando": 12.0}
    await nucleo.emitir_podium(sala, final=True)
    for mensaje in ws_pantalla.enviados + ws_mando.enviados:
        _sin_clave_puntos(mensaje, mensaje.get("type", "?"))


def main() -> None:
    probar_formula_solo_tiempo()
    probar_formula_puntuacion()
    probar_empate_puntuacion_no_tiene_ganador()
    probar_fallos_escritura()
    probar_sumar_puntuacion()
    asyncio.run(probar_ronda_pajaros_usa_tiempo_y_errores())
    asyncio.run(probar_ronda_pajaros_sin_respuesta_cuenta_error())
    asyncio.run(probar_ronda_pajaros_acumula_entre_rondas())
    asyncio.run(probar_ronda_escritura_suma_intentos_fallidos())
    asyncio.run(probar_ronda_escritura_sin_respuesta())
    probar_resumen_clasico_no_suma_puntos_acumulados()
    asyncio.run(probar_escritura_sin_respuesta_no_cuenta_letras_correctas())
    asyncio.run(probar_difusion_fiesta_oculta_metricas_de_desglose())
    probar_sin_api_antigua_de_puntos()
    asyncio.run(probar_mensajes_finales_sin_puntos())
    print("OK - Fórmula puntuación compartida y clásicos")


if __name__ == "__main__":
    main()
