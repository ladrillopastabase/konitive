"""Regresiones de la revisión: respuestas tardías y vuelto tramposo.

Llama al árbitro directamente, sin servidor ni sockets.
"""
from __future__ import annotations

import asyncio
import time

import servidor
from arbitro import nucleo
from servidor import Jugador, Sala, manejar_respuesta_mini


def sala_con_jugador(juego: str, reto: dict) -> tuple[Sala, Jugador]:
    sala = Sala(codigo="TEST1", host_id="yo", modo="individual", capacidad=1)
    jugador = Jugador(id="yo", nombre="YO", ws=None)  # enviar() tolera ws=None
    sala.jugadores["yo"] = jugador
    sala.fase = juego
    sala.datos.update({"reto": reto, "ronda": 1, "momento_respuesta": time.monotonic()})
    jugador.progreso = {"secuencia": [], "fallos": 0, "inicio": None, "fin": None}
    return sala, jugador


async def tocar(sala: Sala, jugador: Jugador, juego: str, respuesta) -> None:
    await manejar_respuesta_mini(
        sala, jugador, {"ronda": 1, "respuesta": respuesta}, juego
    )


async def memoria_cierra_tras_error() -> None:
    reto = {"celdas": 9, "cantidad": 3, "posiciones": {"1": 4, "2": 0, "3": 8}}
    sala, jugador = sala_con_jugador("memoria", reto)
    await tocar(sala, jugador, "memoria", 4)  # bien
    await tocar(sala, jugador, "memoria", 1)  # mal: la ronda se cierra
    await tocar(sala, jugador, "memoria", 0)  # ya no debe contar
    await tocar(sala, jugador, "memoria", 8)
    assert jugador.progreso["secuencia"] == [4], jugador.progreso["secuencia"]


async def memoria_no_revienta_al_terminar() -> None:
    reto = {"celdas": 9, "cantidad": 3, "posiciones": {"1": 4, "2": 0, "3": 8}}
    sala, jugador = sala_con_jugador("memoria", reto)
    for celda in (4, 0, 8, 2):  # el 2 llega después de completar
        await tocar(sala, jugador, "memoria", celda)
    assert jugador.progreso["secuencia"] == [4, 0, 8]


async def vuelto_rechaza_trampas() -> None:
    reto = {"vuelto": 500, "optimo": {"500": 1}}
    for trampa in ({"1000": 1, "500": -1}, {"9" * 5000: 0}, {"7": 1}):
        sala, jugador = sala_con_jugador("vuelto", reto)
        await tocar(sala, jugador, "vuelto", trampa)
        assert jugador.progreso["fallos"] == 1, trampa
    sala, jugador = sala_con_jugador("vuelto", reto)
    await tocar(sala, jugador, "vuelto", {"100": 5})
    assert jugador.progreso["fallos"] == 0 and jugador.progreso["optimo"] is False


class ReconocedorLento:
    """Tarda un poco, como el modelo real bajo carga, y siempre lee un 7."""

    def reconocer(self, trazos):
        time.sleep(0.05)
        return "7", 0.9, []


async def envio_doble_cuenta_una_vez() -> None:
    nucleo.reconocedor_digitos = ReconocedorLento()
    sala, jugador = sala_con_jugador("triangulos", {})
    jugador.progreso.update(
        {"esperado": "7", "digitos": [{"estado": "pendiente", "intentos": 0, "motivo": ""}]}
    )
    mensaje = {"ronda": 1, "index": 0, "trazos": [[[0.5, 0.1], [0.5, 0.9]]]}
    await asyncio.gather(
        *(manejar_respuesta_mini(sala, jugador, mensaje, "triangulos") for _ in range(3))
    )
    casilla = jugador.progreso["digitos"][0]
    assert casilla["intentos"] == 1 and casilla["estado"] == "aceptada", casilla


def tope_de_salas() -> None:
    from fastapi.testclient import TestClient

    servidor.salas.update({f"X{i}": None for i in range(servidor.MAX_SALAS)})
    try:
        with TestClient(servidor.app).websocket_connect("/ws") as ws:
            ws.send_json({"type": "create", "nombre": "YO"})
            assert ws.receive_json()["type"] == "error"
    finally:
        servidor.salas.clear()


def relojes_con_periodo() -> None:
    """Con a. m./p. m. la diferencia se deduce sin ambigüedad de los relojes."""
    from juego.minijuegos import generar_reloj

    def minuto_del_dia(reloj, periodo):
        return (reloj[0] % 12) * 60 + reloj[1] + (720 if periodo == "P. M." else 0)

    for ronda in range(1, 11):
        for _ in range(50):
            r = generar_reloj(ronda)
            diff = (minuto_del_dia(r["reloj2"], r["periodo2"])
                    - minuto_del_dia(r["reloj1"], r["periodo1"])) % 1440
            assert diff == r["horas"] * 60 + r["minutos"], r


def cajas_tapadas_se_detectan() -> None:
    """La caja (0,0,0) queda justo detrás de la (1,1,1): debe contar como oculta."""
    from juego.cajas import contar_visibles

    tapada = [[1, 0], [0, 2]]
    assert contar_visibles(tapada) == 2, contar_visibles(tapada)
    libre = [[0, 1], [1, 2]]
    assert contar_visibles(libre) == 4, contar_visibles(libre)


async def main() -> None:
    relojes_con_periodo()
    cajas_tapadas_se_detectan()
    await envio_doble_cuenta_una_vez()
    await memoria_cierra_tras_error()
    await memoria_no_revienta_al_terminar()
    await vuelto_rechaza_trampas()
    print("OK - Regresiones de la revisión correctas")


if __name__ == "__main__":
    asyncio.run(main())
    tope_de_salas()
    print("OK - Envío doble y tope de salas correctos")
