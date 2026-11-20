"""El avance en vivo y el podio son exclusivos de la pantalla en FIESTA.

Comprueba que los mandos nunca reciben marcadores, conteos ni avances ajenos,
y que el progreso de los minijuegos va privadamente a cada celular sin filtrar
la respuesta correcta.
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


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


nucleo.pausa = pausa_corta

config = uvicorn.Config(servidor.app, host="127.0.0.1", port=8771, log_level="error")
servidor_uvicorn = uvicorn.Server(config)
threading.Thread(target=servidor_uvicorn.run, daemon=True).start()
while not servidor_uvicorn.started:
    time.sleep(0.02)

URL = "ws://127.0.0.1:8771/ws"
CLAVES_AJENAS = ("marcador", "conteos", "confirmados", "podio", "antes", "despues")


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
    cliente = Cliente(await websockets.connect(URL))
    await cliente.enviar(mensaje)
    return cliente


def sin_datos_ajenos(cliente):
    for mensaje in cliente.recibidos:
        for clave in CLAVES_AJENAS:
            assert clave not in mensaje, (clave, mensaje)


async def main():
    host = await conectar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]
    mandos = [
        await conectar({"type": "join", "nombre": nombre, "codigo": codigo})
        for nombre in ("Ana", "Beto")
    ]

    await host.enviar(
        {
            "type": "start",
            "juegos": ["pajaros"],
            "ajustes": {"pajaros": {"rondas": 1, "dificultad": "facil"}},
        }
    )
    show = await host.esperar("birds_show")
    await host.esperar("birds_hide")
    for mando in mandos:
        mando_show = await mando.esperar("birds_show")
        await mando.enviar(
            {
                "type": "bird_answer",
                "count": len(show["aves"]),
                "token": mando_show["token"],
            }
        )

    avance = await host.esperar("progreso_vivo")
    assert avance["juego"] == "pajaros", avance
    assert len(avance["jugadores"]) == 2, avance
    assert all(fila["total"] is None for fila in avance["jugadores"]), avance
    for mando in mandos:
        assert not mando.de_tipo("progreso_vivo"), mando.de_tipo("progreso_vivo")
        sin_datos_ajenos(mando)

    podio = await host.esperar("podium_update")
    assert podio["nombre_juego"] == "HÁMSTERS", podio
    for mando in mandos:
        assert not mando.de_tipo("podium_update"), mando.de_tipo("podium_update")
        await mando.esperar("back_to_selector")
    await host.esperar("back_to_selector")

    await host.enviar(
        {
            "type": "start",
            "juegos": ["stroop"],
            "ajustes": {"stroop": {"rondas": 1, "dificultad": "facil"}},
        }
    )
    show_stroop = await host.esperar("stroop_show")
    write = await host.esperar("stroop_write")
    for mando in mandos:
        await mando.enviar(
            {
                "type": "stroop_answer",
                "ronda": write["ronda"],
                "respuesta": show_stroop["tinta"],
            }
        )
    await asyncio.sleep(0.1)

    # El avance del minijuego se proyecta agregado; el detalle es privado.
    assert not host.de_tipo("mini_progreso"), host.de_tipo("mini_progreso")
    for mando in mandos:
        progresos = mando.de_tipo("mini_progreso")
        assert len(progresos) == 1, progresos
        assert "acepta" not in progresos[0], progresos[0]
        assert progresos[0]["pid"] == mando.recibidos[0]["id"], progresos[0]
        sin_datos_ajenos(mando)

    avances_stroop = [m for m in host.de_tipo("progreso_vivo") if m["juego"] == "stroop"]
    assert avances_stroop, host.de_tipo("progreso_vivo")
    texto = json.dumps(avances_stroop, ensure_ascii=False)
    assert show_stroop["tinta"] not in texto, (show_stroop, texto)
    assert show_stroop.get("palabra") not in texto, (show_stroop, texto)

    await host.esperar("podium_update")
    await host.enviar({"type": "finish_fiesta"})
    await host.esperar("podium_final")
    for mando in mandos:
        assert not mando.de_tipo("podium_final"), mando.de_tipo("podium_final")
        await mando.esperar("fin_fiesta")

    for cliente in (host, *mandos):
        await cliente.cerrar()
    await asyncio.sleep(0.1)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("OK - Avance en vivo y podio solo en pantalla; mandos sin puntos ajenos")


if __name__ == "__main__":
    asyncio.run(main())
