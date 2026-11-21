"""Pruebas del generador y de la partida de «Piedra · Papel · Tijera».

La consigna es invertida: ciertas rondas piden ganar contra la mano que muestra
el rival y el resto piden perder a propósito. La respuesta correcta es siempre
una mano distinta de la del rival. Además se juega en INDIVIDUAL con cliente
WebSocket para comprobar la validación de respuestas y el resumen final.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

import uvicorn
import websockets

import servidor
from arbitro import nucleo
from juego.minijuegos import (
    JUEGOS_MINI, NOMBRES_MINI, RONDAS_MINI, generar, generar_ppt, mana_para,
)
from arbitro.nucleo import JUEGOS_FIESTA, NOMBRES_JUEGOS
from arbitro.minijuegos import (
    MINIJUEGOS_SOLO_PANTALLA, SECRETOS_MINI, TIEMPO_RESPUESTA_MINI,
    VISUAL_MINI, datos_para_resultado, estimulo_para_mando, visual_mini,
)

BASE = Path(__file__).parent


def probar_cliente_incluye_ppt_en_selector_y_mensajes():
    html = (BASE / "static/index.html").read_text(encoding="utf-8")
    js = (BASE / "static/app.js").read_text(encoding="utf-8")
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    assert 'data-juego="ppt"' in html
    assert '"ppt"' in js
    assert "ppt_answer" in js
    assert ".ppt-opcion" in css


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


nucleo.pausa = pausa_corta

config = uvicorn.Config(servidor.app, host="127.0.0.1", port=8782, log_level="error")
servidor_uvicorn = uvicorn.Server(config)
threading.Thread(target=servidor_uvicorn.run, daemon=True).start()
while not servidor_uvicorn.started:
    time.sleep(0.02)

URL = "ws://127.0.0.1:8782/ws"


class Cliente:
    def __init__(self, ws):
        self.ws = ws
        self.recibidos = []
        self.tarea = asyncio.create_task(self._leer())

    async def _leer(self):
        try:
            async for crudo in self.ws:
                self.recibidos.append(json.loads(crudo))
        except websockets.ConnectionClosed:
            pass

    async def enviar(self, objeto):
        await self.ws.send(json.dumps(objeto))

    def de_tipo(self, tipo):
        return [m for m in self.recibidos if m["type"] == tipo]

    async def esperar(self, tipo, timeout=10, desde=0):
        fin = time.monotonic() + timeout
        while True:
            encontrados = self.de_tipo(tipo)
            if len(encontrados) > desde:
                return encontrados[-1]
            assert time.monotonic() < fin, (
                f"No llegó {tipo}. Tipos vistos: {[m['type'] for m in self.recibidos]}"
            )
            await asyncio.sleep(0.01)

    async def cerrar(self):
        self.tarea.cancel()
        await self.ws.close()


async def abrir_individual_ppt() -> Cliente:
    cliente = Cliente(await websockets.connect(URL))
    await cliente.enviar({"type": "individual", "nombre": "PPT", "juegos": ["ppt"]})
    bienvenida = await cliente.esperar("room_created")
    assert bienvenida["juegos"] == ["ppt"], bienvenida
    return cliente


async def responder_ronda(
    cliente: Cliente, mensaje_show: dict, mano: str | None = None
) -> None:
    if mano is None:
        mano = mana_para(mensaje_show["rival"], mensaje_show["objetivo"])
    await cliente.enviar(
        {
            "type": "ppt_answer",
            "ronda": mensaje_show["ronda"],
            "respuesta": mano,
        }
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


def probar_documentacion_incluye_ppt():
    readme = (BASE / "README.md").read_text(encoding="utf-8")
    product = (BASE / "PRODUCT.md").read_text(encoding="utf-8")
    assert "PIEDRA · PAPEL · TIJERA" in readme
    assert "test_ppt.py" in readme
    assert "13 pruebas" in readme
    assert "13 pruebas" in product


async def probar_ppt_individual_responde_bien_y_resume() -> None:
    cliente = await abrir_individual_ppt()
    vistos: set[int] = set()
    fin = time.monotonic() + 30
    while time.monotonic() < fin:
        for indice, mensaje in enumerate(cliente.recibidos):
            if indice in vistos:
                continue
            vistos.add(indice)
            if mensaje["type"] == "ppt_show":
                await responder_ronda(cliente, mensaje)
        if cliente.de_tipo("individual_summary"):
            break
        await asyncio.sleep(0.01)

    resumen = await cliente.esperar("individual_summary")
    datos = resumen["resumen"]["ppt"]
    assert datos["rondas"] == 10
    assert datos["aciertos"] == 10
    assert datos["errores"] == 0
    assert datos["precision"] == 100.0
    assert datos["brain_age"] >= 0 and "puntos" not in datos
    assert len(cliente.de_tipo("ppt_show")) == 10
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
    print("Individual ppt: 10 rondas correctas y resumen completo")


async def probar_ppt_ignora_respuestas_invalidas_y_empate() -> None:
    cliente = await abrir_individual_ppt()
    vistos: set[int] = set()
    fin = time.monotonic() + 30
    while time.monotonic() < fin:
        for indice, mensaje in enumerate(cliente.recibidos):
            if indice in vistos:
                continue
            vistos.add(indice)
            if mensaje["type"] != "ppt_show":
                continue
            ronda = mensaje["ronda"]
            if ronda == 1:
                # Mayúsculas: no es una mano válida, no llega el feedback.
                await responder_ronda(cliente, mensaje, "PIEDRA")
                await responder_ronda(cliente, mensaje)
            elif ronda == 2:
                # La mano del rival nunca es la respuesta: cuenta como error y
                # la respuesta correcta posterior se ignora (ronda ya cerrada).
                await responder_ronda(cliente, mensaje, mensaje["rival"])
                await responder_ronda(cliente, mensaje)
            elif ronda == 3:
                # Ronda anterior: se descarta; después llega la correcta.
                await cliente.enviar(
                    {
                        "type": "ppt_answer",
                        "ronda": ronda - 1,
                        "respuesta": mana_para(mensaje["rival"], mensaje["objetivo"]),
                    }
                )
                await responder_ronda(cliente, mensaje)
            else:
                await responder_ronda(cliente, mensaje)
        if cliente.de_tipo("individual_summary"):
            break
        await asyncio.sleep(0.01)

    resumen = await cliente.esperar("individual_summary")
    datos = resumen["resumen"]["ppt"]
    assert datos["aciertos"] == 9
    assert datos["errores"] == 1
    assert datos["precision"] == 90.0
    assert len(cliente.de_tipo("ppt_feedback")) == 10
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
    print("Individual ppt: respuestas inválidas y fuera de ronda ignoradas")


async def probar_ppt_fiesta_no_filtra_la_respuesta() -> None:
    host = Cliente(await websockets.connect(URL))
    await host.enviar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]

    mandos = []
    for nombre in ("Ana", "Beto"):
        mando = Cliente(await websockets.connect(URL))
        await mando.enviar({"type": "join", "nombre": nombre, "codigo": codigo})
        mandos.append(mando)
    ids_mandos = {(await mando.esperar("room_joined"))["id"] for mando in mandos}

    await host.enviar(
        {
            "type": "start",
            "juegos": ["ppt"],
            "ajustes": {"ppt": {"rondas": 3, "dificultad": "facil"}},
        }
    )

    shows = []
    for ronda in range(3):
        show_pantalla = await host.esperar("ppt_show", desde=ronda)
        assert show_pantalla["ronda"] == ronda + 1, show_pantalla
        shows.append(show_pantalla)
        assert {"rival", "objetivo"} <= show_pantalla.keys(), show_pantalla
        assert "esperado" not in show_pantalla, show_pantalla
        write_pantalla = await host.esperar("ppt_write", desde=ronda)
        assert write_pantalla["ronda"] == ronda + 1, write_pantalla
        assert {"rival", "objetivo"} <= write_pantalla.keys(), write_pantalla
        assert "esperado" not in write_pantalla, write_pantalla
        mano = mana_para(show_pantalla["rival"], show_pantalla["objetivo"])
        for mando in mandos:
            show_mando = await mando.esperar("ppt_show", desde=ronda)
            assert show_mando["ronda"] == ronda + 1, show_mando
            assert not ({"rival", "objetivo", "esperado"} & show_mando.keys()), show_mando
            assert show_mando.get("mira") is True, show_mando
            write_mando = await mando.esperar("ppt_write", desde=ronda)
            assert write_mando["ronda"] == ronda + 1, write_mando
            assert "esperado" not in write_mando, write_mando
            await mando.enviar(
                {
                    "type": "ppt_answer",
                    "ronda": show_pantalla["ronda"],
                    "respuesta": mano,
                }
            )
        result_pantalla = await host.esperar("ppt_result", desde=ronda)
        assert result_pantalla["ronda"] == ronda + 1, result_pantalla
        assert (
            result_pantalla["reto"]["esperado"]
            == mana_para(show_pantalla["rival"], show_pantalla["objetivo"])
        ), result_pantalla
        for mando in mandos:
            result_mando = await mando.esperar("ppt_result", desde=ronda)
            assert result_mando["ronda"] == ronda + 1, result_mando
            assert set(result_mando) <= {"type", "ronda"}, result_mando

    consignas = {show["objetivo"] for show in shows}
    assert consignas == {"ganar", "perder"}, consignas

    podio = await host.esperar("podium_update")
    assert {fila["id"] for fila in podio["despues"]} == ids_mandos, podio
    assert not host.de_tipo("podium_final"), host.de_tipo("podium_final")
    for mando in mandos:
        assert not mando.de_tipo("podium_update"), mando.de_tipo("podium_update")

    for cliente in (host, *mandos):
        await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
    print("Fiesta ppt: mandos sin secretos; consignas y podio solo en pantalla")


async def main() -> None:
    probar_cliente_incluye_ppt_en_selector_y_mensajes()
    print("Cliente: selector y mensajes de ppt presentes")
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
    probar_documentacion_incluye_ppt()
    print("Documentación: piedra papel tijera y 13 pruebas documentadas")
    await probar_ppt_individual_responde_bien_y_resume()
    await probar_ppt_ignora_respuestas_invalidas_y_empate()
    await probar_ppt_fiesta_no_filtra_la_respuesta()
    print("\nOK - Piedra papel tijera correcto")


if __name__ == "__main__":
    asyncio.run(main())
