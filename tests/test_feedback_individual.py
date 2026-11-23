"""Cada jugador recibe su propio acierto o error; la pantalla compartida no.

CAJAS y HÁMSTERS callaban al mando en modo FIESTA: el informe global decía
"CORRECTO" sin saber de quién. Aquí se comprueba que el resultado viaja por un
canal privado por jugador, sin filtrar el total, las aves ni los demás.
"""
from __future__ import annotations

from apoyo import cliente_js, conectar, levantar_servidor  # primero: deja la raíz del proyecto en sys.path

import asyncio
import json
import time

import websockets

import servidor
from arbitro import nucleo


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


nucleo.pausa = pausa_corta

URL = levantar_servidor()
SECRETOS = ("alturas", "total", "visibles", "esperado", "aves", "jugadores", "despues")

PROHIBIDAS = (
    "PUNTOS TOTALES", "<b>${msg.puntos} PUNTOS</b>", 'case "mis_puntos"',
    '"konitive_cajas_record"', '"konitive_operaciones_record"',
    "msg.puntos > anterior", "fila.puntos",
)
NECESARIAS = ('case "mi_brain_age"', "brain_age_juego", "BRAIN AGE TOTAL · MENOR ES MEJOR")


def probar_cliente_solo_tiempo() -> None:
    js = cliente_js()
    for texto in PROHIBIDAS:
        assert texto not in js, f"Queda código de puntos: {texto}"
    for texto in NECESARIAS:
        assert texto in js, f"Falta el contrato de tiempo: {texto}"


async def main():
    probar_cliente_solo_tiempo()
    host = await conectar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]
    mandos = [
        await conectar({"type": "join", "nombre": nombre, "codigo": codigo})
        for nombre in ("Ana", "Beto")
    ]
    ids = [(await mando.esperar("room_joined"))["id"] for mando in mandos]

    # CAJAS: Ana acierta, Beto no. Cada uno debe recibir SOLO su resultado.
    await host.enviar(
        {
            "type": "start",
            "juegos": ["cajas"],
            "ajustes": {"cajas": {"rondas": 1, "dificultad": "facil"}},
        }
    )
    pila = await host.esperar("cajas_show")
    await host.esperar("cajas_hide")
    for mando, cuenta in zip(mandos, (pila["total"], pila["total"] + 2)):
        await mando.esperar("cajas_show")
        await mando.enviar({"type": "cajas_answer", "count": cuenta})

    for mando, pid, acierto in zip(mandos, ids, (True, False)):
        fb = await mando.esperar("cajas_feedback")
        assert fb["pid"] == pid, fb
        assert fb["acepta"] is acierto, fb
        for clave in SECRETOS:
            assert clave not in fb, (clave, fb)
        aviso_ronda = mando.de_tipo("cajas_result")
        assert aviso_ronda, aviso_ronda
        assert all("acierto" not in m for m in aviso_ronda), aviso_ronda

    await host.esperar("back_to_selector")
    await asyncio.sleep(0.05)

    # HÁMSTERS: el mismo contrato, sin revelar el recuento correcto.
    await host.enviar(
        {
            "type": "start",
            "juegos": ["pajaros"],
            "ajustes": {"pajaros": {"rondas": 1, "dificultad": "facil"}},
        }
    )
    show = await host.esperar("birds_show")
    correcto = len(show["aves"])
    await host.esperar("birds_hide")
    for mando, cuenta in zip(mandos, (correcto, correcto + 2)):
        mando_show = await mando.esperar("birds_show")
        await mando.enviar(
            {"type": "bird_answer", "count": cuenta, "token": mando_show["token"]}
        )

    for mando, pid, acierto in zip(mandos, ids, (True, False)):
        fb = await mando.esperar("round_feedback")
        assert fb["pid"] == pid, fb
        assert fb["juego"] == "pajaros", fb
        assert fb["acepta"] is acierto, fb
        for clave in SECRETOS:
            assert clave not in fb, (clave, fb)
        aviso_ronda = mando.de_tipo("round_result")
        assert aviso_ronda, aviso_ronda
        assert all("esperado" not in m and "puntos" not in m for m in aviso_ronda), aviso_ronda

    await host.esperar("back_to_selector")
    await asyncio.sleep(0.05)
    await host.enviar({"type": "finish_fiesta"})
    await host.esperar("podium_final")

    js = cliente_js()
    assert "cajas_feedback:" in js
    assert "round_feedback:" in js
    # Ni barras de espera inútiles ni un "CORRECTO" global en la pantalla.
    assert "barraDuracion" not in js
    assert "RONDA CORRECTA" not in js
    assert "¡CORRECTO!" not in js

    for cliente in (host, *mandos):
        await cliente.cerrar()
    await asyncio.sleep(0.1)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("OK - Acierto o error privado por jugador, sin barra ni CORRECTO global")


if __name__ == "__main__":
    asyncio.run(main())
