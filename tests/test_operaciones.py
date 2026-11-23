"""Pruebas del minijuego «Operaciones Matemáticas».

Valida la generación de operaciones (0-99, sin negativos, sin repetir la
anterior), una tanda individual completa por WebSocket y una fiesta con dos
mandos para comprobar que los mandos nunca reciben el enunciado.

El reconocedor de cifras se parchea para poder «escribir» cualquier dígito
codificándolo en la x del primer punto del trazo.
"""
from __future__ import annotations

from apoyo import Cliente, levantar_servidor  # primero: deja la raíz del proyecto en sys.path

import asyncio
import json
import time

import websockets

import servidor
from arbitro import nucleo
from arbitro.puntuacion import brain_age
from juego.operaciones import generar_operacion, nivel_para


class ReconocedorFalso:
    """Decodifica la cifra esperada desde la x del primer punto del trazo."""

    def reconocer(self, trazos):
        x = trazos[0][0][0]
        indice = max(0, min(9, round(x * 10) - 1))
        return str(indice), 0.99, [0.0] * 10


nucleo.reconocedor_digitos = ReconocedorFalso()


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


nucleo.pausa = pausa_corta

URL = levantar_servidor()


def codigo_digito(digito: int):
    x = (digito + 1) / 10
    return [[[x, 0.2], [x, 0.8]]]


async def escribir_resultado(cliente, resultado: str):
    for indice, digito in enumerate(resultado):
        await cliente.enviar(
            {"type": "digit", "index": indice, "trazos": codigo_digito(int(digito))}
        )


def resultado_de(texto: str) -> str:
    a, operador, b = texto.split(" ")
    a, b = int(a), int(b)
    total = {"+": a + b, "−": a - b, "×": a * b}[operador]
    return str(total)


def validar_generacion() -> None:
    for ronda in range(1, 11):
        indice, nombre = nivel_para(ronda)
        anterior = None
        for _ in range(80):
            operacion = generar_operacion(ronda, anterior)
            assert operacion["nivel"] == indice + 1
            assert operacion["dificultad"] == nombre
            assert operacion["texto"] != anterior
            assert operacion["resultado"].isdigit()
            assert 0 <= int(operacion["resultado"]) <= 99
            assert operacion["operador"] in ("+", "−", "×")
            assert resultado_de(operacion["texto"]) == operacion["resultado"]
            anterior = operacion["texto"]
    print("Generación: sumas, restas y productos con resultado de 0 a 99, correcto")


async def jugar_individual() -> None:
    ws = await websockets.connect(URL)
    cliente = Cliente(ws)
    await cliente.enviar({"type": "operaciones", "nombre": "Solo"})
    bienvenida = await cliente.esperar("room_created")
    assert bienvenida["modo"] == "operaciones"
    yo = bienvenida["id"]

    texto = ""
    vistos_show = 0
    vistos_write = 0
    fin = time.monotonic() + 20
    while time.monotonic() < fin:
        shows = cliente.de_tipo("operacion_show")
        if len(shows) > vistos_show:
            texto = shows[-1]["texto"]
            vistos_show = len(shows)
        writes = cliente.de_tipo("operacion_write")
        if len(writes) > vistos_write:
            vistos_write = len(writes)
            await escribir_resultado(cliente, resultado_de(texto))
        if cliente.de_tipo("operacion_over"):
            break
        await asyncio.sleep(0.01)
    assert cliente.de_tipo("operacion_over"), "La tanda individual no terminó"

    sobre = cliente.de_tipo("operacion_over")[0]
    assert sobre["rondas"] == 10
    assert len(cliente.de_tipo("operacion_show")) == 10
    assert len(cliente.de_tipo("digit_feedback")) >= 10
    assert len(cliente.de_tipo("operacion_result")) == 10
    for mensaje in cliente.de_tipo("digit_feedback"):
        assert mensaje["aceptada"] is True, mensaje
    for mensaje in cliente.de_tipo("operacion_result"):
        dato = mensaje["desglose"][yo]
        assert not {"digitos", "bono"} & dato.keys(), dato
        assert dato["brain_age"] >= brain_age(
            dato["tiempo"], dato["errores"]
        ) - 0.05, dato
        assert "total" not in dato, dato
        assert dato["errores"] == 0
        assert dato["automaticas"] == 0
        assert mensaje["resultado"] == resultado_de(mensaje["texto"])
    assert sobre["brain_age"] == brain_age(
        sobre["tiempo_total"], sobre["errores"]
    ), sobre
    assert "puntos" not in sobre, sobre

    await cliente.enviar({"type": "operaciones_restart"})
    reinicio = await cliente.esperar("match_start")
    assert reinicio["modo"] == "operaciones"
    await cliente.cerrar()
    print("Individual: 10 rondas, cifras manuscritas y reinicio correctos")


async def jugar_fiesta() -> None:
    host_ws = await websockets.connect(URL)
    host = Cliente(host_ws)
    await host.enviar({"type": "fiesta", "nombre": "Pantalla"})
    bienvenida = await host.esperar("room_created")
    assert bienvenida["modo"] == "fiesta"
    codigo = bienvenida["codigo"]
    host_id = bienvenida["id"]

    mandos = []
    for nombre in ("Ana", "Beto"):
        ws = await websockets.connect(URL)
        mando = Cliente(ws)
        await mando.enviar({"type": "join", "nombre": nombre, "codigo": codigo})
        unido = await mando.esperar("room_joined")
        assert unido["rol"] == "mando", unido
        mandos.append((mando, unido["id"]))

    await host.enviar({"type": "start", "juego": "operaciones"})

    fin = time.monotonic() + 20
    while not host.de_tipo("operacion_over") and time.monotonic() < fin:
        shows = host.de_tipo("operacion_show")
        if not shows:
            await asyncio.sleep(0.01)
            continue
        numero = len(shows)
        texto = shows[-1]["texto"]

        # La pantalla ve el enunciado; los mandos jamás deben recibirlo.
        for mando, _ in mandos:
            show_mando = mando.de_tipo("operacion_show")
            if len(show_mando) >= numero:
                assert "texto" not in show_mando[numero - 1], show_mando[numero - 1]

        writes = [m.de_tipo("operacion_write") for m, _ in mandos]
        if all(len(w) >= numero for w in writes):
            resultado = resultado_de(texto)
            await escribir_resultado(mandos[0][0], resultado)
            # El segundo mando completa todas las cifras, pero se equivoca a
            # propósito: así se comprueba el desempate del podio.
            equivocado = "1" * len(resultado)
            if equivocado == resultado:
                equivocado = "2" * len(resultado)
            await escribir_resultado(mandos[1][0], equivocado)
        await asyncio.sleep(0.01)

    assert host.de_tipo("operacion_over"), "La fiesta de operaciones no terminó"
    assert len(host.de_tipo("operacion_show")) == nucleo.RONDAS_FIESTA
    assert host.de_tipo("progreso_vivo"), "La pantalla no recibió el avance de cifras"
    for mando, _ in mandos:
        assert not mando.de_tipo("progreso_vivo"), "El mando no debe ver avances ajenos"
        shows = mando.de_tipo("operacion_show")
        assert len(shows) == nucleo.RONDAS_FIESTA
        assert all("texto" not in show for show in shows)
        # El enunciado resuelto y el desglose solo llegan a la pantalla.
        informes = mando.de_tipo("operacion_result")
        assert len(informes) == nucleo.RONDAS_FIESTA
        assert all(
            not any(
                c in informe
                for c in ("texto", "resultado", "desglose", "clasificacion")
            )
            for informe in informes
        ), informes
        # El podio (con los tiempos de todos) solo se proyecta en la pantalla.
        assert not mando.de_tipo("podium_update"), mando.de_tipo("podium_update")

    podio = await host.esperar("podium_update")
    brain_ages = podio["brain_age_juego"]
    assert host_id not in brain_ages, brain_ages
    assert {m[1] for m in mandos}.issubset(brain_ages), brain_ages
    assert podio["nombre_juego"] == "OPERACIONES"
    assert podio["despues"][0]["brain_age"] == min(brain_ages.values())

    await host.esperar("back_to_selector")
    for mando, _ in mandos:
        await mando.esperar("back_to_selector")
        await mando.cerrar()
    await host.cerrar()
    print("Fiesta: dos mandos escriben cifras, sin enunciado y con podio correcto")


async def main():
    validar_generacion()
    await jugar_individual()
    await jugar_fiesta()
    await asyncio.sleep(0.1)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("\nOK - Operaciones Matemáticas correcto")


if __name__ == "__main__":
    asyncio.run(main())
