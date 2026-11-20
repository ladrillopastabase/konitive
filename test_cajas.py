"""Pruebas del minijuego Cuenta Cajas.

Por un lado valida la generación de pilas (total, columnas sólidas, cajas
visibles y dificultad) y por otro juega una tanda completa de 10 rondas por
WebSocket con las pausas acortadas. La respuesta se envía como `count`, igual
que en el contador de pájaros. No toca el protocolo de los minijuegos
existentes.
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
from juego.cajas import DIFICULTADES, contar_visibles, generar_pila, suma_total


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


nucleo.pausa = pausa_corta

config = uvicorn.Config(servidor.app, host="127.0.0.1", port=8766, log_level="error")
servidor_uvicorn = uvicorn.Server(config)
threading.Thread(target=servidor_uvicorn.run, daemon=True).start()
while not servidor_uvicorn.started:
    time.sleep(0.02)

URL = "ws://127.0.0.1:8766/ws"


def validar_pila(pila: dict, indice: int) -> None:
    alturas = pila["alturas"]
    base = alturas[0].__len__()
    assert base == DIFICULTADES[indice][1]
    assert base >= 5, "La cuadrícula de cajas debe ser al menos 5×5"
    assert len(alturas) == base
    _, _, minimo, maximo, tope, segundos = DIFICULTADES[indice]
    assert minimo <= pila["total"] <= maximo
    assert suma_total(alturas) == pila["total"], alturas
    assert pila["segundos"] == segundos
    assert all(0 <= h <= tope for fila in alturas for h in fila)
    assert contar_visibles(alturas) == pila["visibles"]
    assert 0 <= pila["visibles"] <= pila["total"]
    assert pila["ocultas"] == pila["total"] - pila["visibles"]

    # La pila debe ser una forma 2D natural, no una sola diagonal.
    activas = {(x, y) for y, fila in enumerate(alturas) for x, h in enumerate(fila) if h}
    assert len({x + y for x, y in activas}) > 1, "La pila es una sola diagonal"
    assert all(
        any((x + dx, y + dy) in activas for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        for x, y in activas
    ), "La pila tiene casillas aisladas"


def validar_generacion() -> None:
    for indice in range(len(DIFICULTADES)):
        anterior = None
        con_ocultas = 0
        max_ocultas = 0
        for _ in range(120):
            pila = generar_pila(indice, anterior)
            validar_pila(pila, indice)
            if anterior is not None:
                assert pila["alturas"] != anterior, "Se repitió la pila anterior"
            con_ocultas += pila["ocultas"] > 0
            max_ocultas = max(max_ocultas, pila["ocultas"])
            anterior = pila["alturas"]
        # Todas las cajas se ven: no hay objetos invisibles que adivinar.
        assert con_ocultas == 0, f"Pilas con cajas ocultas: {con_ocultas}/120"
        assert max_ocultas == 0, f"Cajas ocultas en una pila: {max_ocultas}"
    print("Generación: totales, columnas sólidas y cero cajas ocultas")


async def jugar_tanda() -> dict:
    mensajes: dict[str, list[dict]] = {}
    async with websockets.connect(URL) as ws:
        await ws.send(json.dumps({"type": "cajas", "nombre": "Solo"}))
        bienvenida = json.loads(await ws.recv())
        assert bienvenida["type"] == "room_created", bienvenida
        assert bienvenida["modo"] == "cajas"

        vistas: list[dict] = []
        anterior = None
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            if msg["type"] == "error":
                raise AssertionError(msg)
            mensajes.setdefault(msg["type"], []).append(msg)
            vistas.append(msg)

            if msg["type"] == "cajas_show":
                pila = {
                    "alturas": msg["alturas"],
                    "base": msg["base"],
                    "total": sum(sum(fila) for fila in msg["alturas"]),
                    "visibles": contar_visibles(msg["alturas"]),
                    "ocultas": msg.get("ocultas", 0),
                    "segundos": msg["duracion"],
                    "dificultad": msg["dificultad"],
                }
                indice = ["FÁCIL", "NORMAL", "DIFÍCIL"].index(msg["dificultad"])
                validar_pila(pila, indice)
                if anterior is not None:
                    assert msg["alturas"] != anterior, "Pila repetida entre rondas"
                anterior = msg["alturas"]

            elif msg["type"] == "cajas_hide":
                # Se confirma siempre la respuesta correcta con el mismo formato
                # que el contador de pájaros, para comprobar la subida de
                # dificultad y el multiplicador por racha.
                total = sum(sum(fila) for fila in vistas[-2]["alturas"])
                await ws.send(json.dumps({"type": "cajas_answer", "count": total}))

            elif msg["type"] == "cajas_result":
                ronda = msg["ronda"]
                nivel = min(3, 1 + (ronda - 1) // 3)
                esperado = ("FÁCIL", "NORMAL", "DIFÍCIL")[nivel - 1]
                multiplicador = nivel
                assert msg["dificultad"] == esperado, (ronda, msg["dificultad"])
                assert msg["multiplicador"] == multiplicador, msg
                assert msg["acierto"] is True, msg
                assert 0 <= msg["bono"] <= 50
                assert msg["puntos"] == (100 + msg["bono"]) * multiplicador, msg
                assert msg["racha"] == ronda, msg
                assert sum(sum(fila) for fila in msg["alturas"]) == msg["total"]

            elif msg["type"] == "cajas_over":
                break

        # La tanda se puede repetir sin reconectar.
        await ws.send(json.dumps({"type": "cajas_restart"}))
        reinicio = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert reinicio["type"] == "match_start", reinicio
        assert reinicio["modo"] == "cajas"
    return mensajes


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

    async def esperar(self, tipo, timeout=10):
        fin = time.monotonic() + timeout
        while True:
            encontrados = self.de_tipo(tipo)
            if encontrados:
                return encontrados[-1]
            assert time.monotonic() < fin, f"No llegó {tipo}"
            await asyncio.sleep(0.01)

    async def cerrar(self):
        self.tarea.cancel()
        await self.ws.close()


async def jugar_fiesta_dos_mandos():
    """Dos mandos responden a la vez: cada uno debe tener su propia puntuación."""
    host_ws = await websockets.connect(URL)
    host = Cliente(host_ws)
    await host.enviar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]

    mandos = []
    ids = []
    for nombre in ("Ana", "Beto"):
        ws = await websockets.connect(URL)
        mando = Cliente(ws)
        await mando.enviar({"type": "join", "nombre": nombre, "codigo": codigo})
        ids.append((await mando.esperar("room_joined"))["id"])
        mandos.append(mando)

    await host.enviar({"type": "start", "juego": "cajas"})
    vistos_show = 0
    vistos_hide = 0
    total = 0
    fin = time.monotonic() + 20
    while not host.de_tipo("cajas_over") and time.monotonic() < fin:
        shows = host.de_tipo("cajas_show")
        if len(shows) > vistos_show:
            vistos_show = len(shows)
            total = sum(sum(fila) for fila in shows[-1]["alturas"])
            for mando in mandos:
                show = mando.de_tipo("cajas_show")
                assert "alturas" not in show[vistos_show - 1]
        hides = host.de_tipo("cajas_hide")
        if len(hides) > vistos_hide:
            vistos_hide = len(hides)
            await mandos[0].enviar({"type": "cajas_answer", "count": total})
            await mandos[1].enviar({"type": "cajas_answer", "count": total + 1})
        await asyncio.sleep(0.01)

    assert host.de_tipo("cajas_over"), "No terminó la fiesta de cajas"
    resultados = host.de_tipo("cajas_result")
    assert len(resultados) == nucleo.RONDAS_FIESTA
    for msg in resultados:
        assert set(msg["jugadores"]) == set(ids), msg
        assert msg["jugadores"][ids[0]]["acierto"] is True
        assert msg["jugadores"][ids[1]]["acierto"] is False
        assert set(msg["marcador"]["cajas"]) == set(ids)
    # El informe de cada ronda se ve solo en la pantalla: los mandos no
    # reciben la pila revelada ni el detalle de aciertos.
    for mando in mandos:
        informes = mando.de_tipo("cajas_result")
        assert len(informes) == nucleo.RONDAS_FIESTA
        assert all(
            not any(
                c in informe
                for c in ("alturas", "total", "visibles", "jugadores", "clasificacion")
            )
            for informe in informes
        ), informes

    sobre = host.de_tipo("cajas_over")[0]
    filas = {fila["id"]: fila for fila in sobre["clasificacion"]}
    assert set(filas) == set(ids)
    assert filas[ids[0]]["puntos"] > filas[ids[1]]["puntos"]
    assert filas[ids[1]]["puntos"] == 0

    await host.esperar("podium_update")
    await asyncio.gather(*(m.cerrar() for m in mandos), host.cerrar())
    print("Fiesta: dos mandos puntúan por separado sin ver la pila")


async def main():
    validar_generacion()
    mensajes = await jugar_tanda()
    await jugar_fiesta_dos_mandos()

    print("\n--- Tanda completa ---")
    print("Mensajes:", {k: len(v) for k, v in mensajes.items()})

    for tipo in ("cajas_countdown", "cajas_show", "cajas_hide", "cajas_result"):
        assert len(mensajes.get(tipo, [])) == 10, f"Faltan mensajes {tipo}"
    assert len(mensajes.get("cajas_over", [])) == 1

    over = mensajes["cajas_over"][0]
    assert over["aciertos"] == 10, over
    assert over["mejor_racha"] == 10, over
    assert over["rondas"] == 10, over
    assert over["puntos"] == sum(m["puntos"] for m in mensajes["cajas_result"])
    print("Puntos totales:", over["puntos"])

    await asyncio.sleep(0.1)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("\nOK - Cuenta Cajas correcto (el resto de modos no se modificó)")


if __name__ == "__main__":
    asyncio.run(main())
