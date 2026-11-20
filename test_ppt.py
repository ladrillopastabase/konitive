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
    assert datos["brain_age"] >= 0 and datos["puntos"] >= 0
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
    await probar_ppt_individual_responde_bien_y_resume()
    await probar_ppt_ignora_respuestas_invalidas_y_empate()
    print("\nOK - Piedra papel tijera correcto")


if __name__ == "__main__":
    asyncio.run(main())
