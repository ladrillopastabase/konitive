"""Piezas comunes de las pruebas: rutas, servidor de prueba, cliente WebSocket
y el código del cliente web.

Cada prueba se ejecuta como script (``python tests/test_x.py``) o con
``python tests/correr.py``. Importar este módulo primero deja la raíz del
proyecto en ``sys.path`` para poder importar ``servidor``, ``arbitro`` y ``juego``.
"""
from __future__ import annotations

import asyncio
import json
import re
import socket
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import uvicorn  # noqa: E402
import websockets  # noqa: E402

URL = ""


def levantar_servidor() -> str:
    """Arranca la app real en un puerto libre y devuelve la URL del WebSocket.

    El puerto libre permite correr todas las pruebas en paralelo.
    """
    global URL
    import servidor

    with socket.socket() as sonda:
        sonda.bind(("127.0.0.1", 0))
        puerto = sonda.getsockname()[1]
    config = uvicorn.Config(servidor.app, host="127.0.0.1", port=puerto, log_level="error")
    instancia = uvicorn.Server(config)
    threading.Thread(target=instancia.run, daemon=True).start()
    while not instancia.started:
        time.sleep(0.02)
    URL = f"ws://127.0.0.1:{puerto}/ws"
    return URL


def cliente_js() -> str:
    """Todo el JavaScript del cliente, en el orden en que lo carga index.html."""
    html = (RAIZ / "static/index.html").read_text(encoding="utf-8")
    rutas = re.findall(r'<script src="/static/([^"]+)"', html)
    return "\n".join((RAIZ / "static" / ruta).read_text(encoding="utf-8") for ruta in rutas)


class Cliente:
    """Jugador simulado: guarda todo lo que recibe y espera mensajes por tipo."""

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
        """El último mensaje `tipo` cuando ya llegaron más de `desde`."""
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


async def conectar(mensaje):
    cliente = Cliente(await websockets.connect(URL))
    await cliente.enviar(mensaje)
    return cliente
