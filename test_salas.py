"""Pruebas del sistema de salas, QR, fiesta y podio.

Ejercita los endpoints HTTP, la unión por código, los roles pantalla/mando,
el aforo de 8 mandos, el filtrado de datos que hay que memorizar y el podio
entre juegos. No altera el protocolo de los modos individuales.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import uvicorn
import websockets

import servidor


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


servidor.pausa = pausa_corta

config = uvicorn.Config(servidor.app, host="127.0.0.1", port=8768, log_level="error")
servidor_uvicorn = uvicorn.Server(config)
threading.Thread(target=servidor_uvicorn.run, daemon=True).start()
while not servidor_uvicorn.started:
    time.sleep(0.02)

BASE = "http://127.0.0.1:8768"
URL = "ws://127.0.0.1:8768/ws"


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
            assert time.monotonic() < fin, (
                f"No llegó {tipo}. Tipos vistos: {[m['type'] for m in self.recibidos]}"
            )
            await asyncio.sleep(0.01)

    async def cerrar(self):
        self.tarea.cancel()
        await self.ws.close()


async def conectar(mensaje):
    ws = await websockets.connect(URL)
    cliente = Cliente(ws)
    await cliente.enviar(mensaje)
    return cliente


async def cerrar_todos(*clientes):
    await asyncio.gather(*(c.cerrar() for c in clientes))
    await asyncio.sleep(0.1)


def probar_http():
    with urllib.request.urlopen(f"{BASE}/api/red") as respuesta:
        datos = json.loads(respuesta.read())
    assert datos["ip"] and datos["puerto"] == 8000, datos

    url = f"{BASE}/api/qr?texto={urllib.parse.quote(BASE + '/?sala=ABC12')}"
    with urllib.request.urlopen(url) as respuesta:
        svg = respuesta.read().decode("utf-8")
        assert respuesta.headers.get_content_type() == "image/svg+xml"
    assert "<svg" in svg and "<path" in svg, svg[:200]

    try:
        urllib.request.urlopen(f"{BASE}/api/qr?texto=")
        raise AssertionError("El QR sin texto debería fallar")
    except urllib.error.HTTPError as error:
        assert error.code == 400
    print("HTTP: /api/red y /api/qr (SVG) correctos")


async def probar_sala_normal():
    host = await conectar({"type": "create", "nombre": "Host"})
    bienvenida = await host.esperar("room_created")
    codigo = bienvenida["codigo"]
    assert len(codigo) == 5

    invitado = await conectar({"type": "join", "nombre": "Invitado", "codigo": codigo})
    unido = await invitado.esperar("room_joined")
    assert "rol" not in unido or unido["rol"] == "jugador"
    assert await host.esperar("player_joined")

    tercero = await conectar({"type": "join", "nombre": "Tercero", "codigo": codigo})
    error = await tercero.esperar("error")
    assert error["mensaje"] == "La sala está llena"

    await cerrar_todos(host, invitado, tercero)
    print("Sala normal: unión por código y aforo de 2 correctos")


async def probar_roles_y_aforo():
    host = await conectar({"type": "fiesta", "nombre": "Pantalla"})
    bienvenida = await host.esperar("room_created")
    assert bienvenida["modo"] == "fiesta"
    assert bienvenida["capacidad"] == 9
    codigo = bienvenida["codigo"]

    mandos = []
    for numero in range(8):
        mando = await conectar(
            {"type": "join", "nombre": f"M{numero}", "codigo": codigo}
        )
        unido = await mando.esperar("room_joined")
        assert unido["rol"] == "mando", unido
        assert unido["capacidad"] == 9
        mandos.append(mando)
    assert len(host.de_tipo("player_joined")) == 8

    nuevo = await conectar({"type": "join", "nombre": "Extra", "codigo": codigo})
    error = await nuevo.esperar("error")
    assert error["mensaje"] == "La sala está llena"

    await cerrar_todos(host, nuevo, *mandos)
    print("Fiesta: 8 mandos, rol correcto y rechazo del noveno correctos")


async def probar_cajas_y_podio():
    host = await conectar({"type": "fiesta", "nombre": "Pantalla"})
    bienvenida = await host.esperar("room_created")
    codigo = bienvenida["codigo"]
    mandos = []
    for nombre in ("Ana", "Beto"):
        mandos.append(
            await conectar({"type": "join", "nombre": nombre, "codigo": codigo})
        )

    await host.enviar({"type": "start", "juego": "cajas"})
    vistos_show = 0
    vistos_hide = 0
    fin = time.monotonic() + 20
    while not host.de_tipo("cajas_over") and time.monotonic() < fin:
        shows = host.de_tipo("cajas_show")
        if len(shows) > vistos_show:
            vistos_show = len(shows)
            alturas = shows[-1]["alturas"]
            total = sum(sum(fila) for fila in alturas)
            # Los mandos ven la cuenta atrás, pero nunca la pila.
            for mando in mandos:
                show = mando.de_tipo("cajas_show")
                assert len(show) >= vistos_show
                assert "alturas" not in show[vistos_show - 1], show[vistos_show - 1]

        hides = host.de_tipo("cajas_hide")
        if len(hides) > vistos_hide:
            vistos_hide = len(hides)
            for mando in mandos:
                await mando.enviar({"type": "cajas_answer", "count": total})
        await asyncio.sleep(0.01)

    assert host.de_tipo("cajas_over"), "No terminó la tanda de cajas en fiesta"
    assert vistos_show == 10 and vistos_hide == 10

    podio = await host.esperar("podium_update")
    assert podio["nombre_juego"] == "CAJAS"
    assert len(podio["antes"]) == 2
    assert all(fila["puntos"] == 0 for fila in podio["antes"])
    assert len(podio["despues"]) == 2
    assert set(podio["puntos_juego"]) == {
        m.recibidos[0]["id"] for m in mandos
    }, podio["puntos_juego"]
    for mando in mandos:
        await mando.esperar("podium_update")
        await mando.esperar("back_to_selector")
    selector = await host.esperar("back_to_selector")
    assert selector["host"] == bienvenida["id"]

    await host.enviar({"type": "finish_fiesta"})
    final = await host.esperar("podium_final")
    assert len(final["despues"]) == 2

    await cerrar_todos(host, *mandos)
    print("Fiesta: cajas sin alturas en mandos, podio y cierre correctos")


async def probar_pajaros_filtrado():
    host = await conectar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]
    mando = await conectar({"type": "join", "nombre": "Ana", "codigo": codigo})

    await host.enviar({"type": "start", "juego": "pajaros"})
    await host.esperar("birds_show")
    show_host = host.de_tipo("birds_show")[-1]
    show_mando = await mando.esperar("birds_show")
    assert show_host["aves"], show_host
    assert "aves" not in show_mando, show_mando

    await cerrar_todos(host, mando)
    print("Fiesta: las aves solo llegan a la pantalla correcto")


async def main():
    probar_http()
    await probar_sala_normal()
    await probar_roles_y_aforo()
    await probar_cajas_y_podio()
    await probar_pajaros_filtrado()
    await asyncio.sleep(0.1)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("\nOK - Salas, QR, fiesta y podio correctos")


if __name__ == "__main__":
    asyncio.run(main())
