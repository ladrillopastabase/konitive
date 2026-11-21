"""Cada jugador recibe su propio acierto o error; la pantalla compartida no.

CAJAS y HÁMSTERS callaban al mando en modo FIESTA: el informe global decía
"CORRECTO" sin saber de quién. Aquí se comprueba que el resultado viaja por un
canal privado por jugador, sin filtrar el total, las aves ni los demás.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import threading
import time
from pathlib import Path

import uvicorn
import websockets

import servidor
from arbitro import nucleo


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


nucleo.pausa = pausa_corta

config = uvicorn.Config(servidor.app, host="127.0.0.1", port=8772, log_level="error")
servidor_uvicorn = uvicorn.Server(config)
threading.Thread(target=servidor_uvicorn.run, daemon=True).start()
while not servidor_uvicorn.started:
    time.sleep(0.02)

URL = "ws://127.0.0.1:8772/ws"
SECRETOS = ("alturas", "total", "visibles", "esperado", "aves", "jugadores", "despues")
RAIZ = Path(__file__).resolve().parent

CODIGO_CLIENTE = r"""
const fs = require('fs');
const js = fs.readFileSync('static/app.js', 'utf8');
const prohibidas = [
  'PUNTOS TOTALES', '<b>${msg.puntos} PUNTOS</b>', 'case "mis_puntos"',
  '"konitive_cajas_record"', '"konitive_operaciones_record"',
  'msg.puntos > anterior', 'fila.puntos'
];
for (const texto of prohibidas) {
  if (js.includes(texto)) throw new Error('Queda código de puntos: ' + texto);
}
const necesarias = [
  'konitive_cajas_record_brain_age', 'konitive_operaciones_record_brain_age',
  'case "mi_brain_age"', 'brain_age_juego', 'BRAIN AGE · MENOR ES MEJOR'
];
for (const texto of necesarias) {
  if (!js.includes(texto)) throw new Error('Falta el contrato de tiempo: ' + texto);
}
const funcion = js.match(/function mejorBrainAge\(clave\) \{[\s\S]*?\n  \}/);
if (!funcion) throw new Error('Falta la lectura del récord con clave nueva');
const mejor = new Function(
  'localStorage', funcion[0] + '; return mejorBrainAge;'
)({ getItem: (clave) => ({ konitive_cajas_record: '980' })[clave] ?? null });
if (mejor('konitive_cajas_record_brain_age') !== Infinity) {
  throw new Error('Un valor de la escala antigua se compara como Brain Age');
}
const anteriorConRécord = new Function(
  'localStorage', funcion[0] + '; return mejorBrainAge;'
)({ getItem: () => '22' });
const coincidencias = [...js.matchAll(/const nuevoRecord = ([^;]+);/g)];
if (coincidencias.length < 2) throw new Error('Faltan las dos comparaciones de récord');
for (const [, expresion] of coincidencias.slice(0, 2)) {
  const compara = new Function('brainAge', 'anterior', 'return ' + expresion + ';');
  if (compara(22, Infinity) !== true) throw new Error('Sin récord previo debe haber récord');
  if (compara(30, 22) !== false) throw new Error('Un Brain Age mayor no debe batir récord');
}
if (anteriorConRécord('konitive_cajas_record_brain_age') !== 22) {
  throw new Error('Un Brain Age guardado no se lee como récord');
}
process.stdout.write('OK');
"""


def probar_cliente_solo_tiempo() -> None:
    resultado = subprocess.run(
        ["node", "-e", CODIGO_CLIENTE],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout == "OK", resultado.stdout


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

    js = (Path(__file__).parent / "static/app.js").read_text(encoding="utf-8")
    assert 'case "cajas_feedback"' in js
    assert 'case "round_feedback"' in js
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
