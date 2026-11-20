import random
from pathlib import Path

from juego.minijuegos import JUEGOS_MINI
from arbitro.nucleo import JUEGOS_FIESTA, NOMBRES_JUEGOS
from juego.rastreo import (
    CELDAS, HAMSTERS, LADOS, BoardManager, CatSpawner,
    HamsterManager, MovementSystem,
)
from juego.rastreo import (
    DifficultyManager, GameManager, NIVELES, RONDAS_RASTREO,
    ScoreManager, SelectionManager,
)

BASE = Path(__file__).parent

def probar_tablero_arranca_con_10_gatos_y_2_hamsters():
    tablero = BoardManager(random.Random(7))
    tablero.inicializar()
    assert len(tablero.instantanea()) == CELDAS == 12
    assert sorted(tablero.instantanea()) == sorted(["G"] * 10 + list(HAMSTERS))

def probar_desplazamientos_en_los_cuatro_lados():
    for lado in LADOS:
        tablero = BoardManager(random.Random(3))
        hamsters = HamsterManager(random.Random(3))
        tablero.inicializar()
        movimiento = MovementSystem(tablero, hamsters).aplicar(lado, 0)
        assert movimiento["lado"] == lado
        assert len(tablero.instantanea()) == 12
        assert sorted(tablero.instantanea()) == sorted(["G"] * 10 + list(HAMSTERS))

def probar_rastreo_no_duplica_ni_pierde_hamsters_tras_200_entradas():
    rng = random.Random(11)
    tablero, hamsters = BoardManager(rng), HamsterManager(rng)
    tablero.inicializar()
    sistema, spawner = MovementSystem(tablero, hamsters), CatSpawner(rng)
    finales = set()
    for _ in range(200):
        lado, linea = spawner.siguiente()
        sistema.aplicar(lado, linea)
        pos = hamsters.posiciones(tablero)
        assert set(pos) == set(HAMSTERS)
        assert len(set(pos.values())) == 2
        finales.update(pos.values())
    assert finales <= set(range(12))

def probar_cuatro_niveles_con_parametros_independientes():
    assert tuple(NIVELES) == ("facil", "normal", "dificil", "experto")
    claves = {"observacion", "movimiento", "entradas", "intervalo", "animacion"}
    for parametros in NIVELES.values():
        assert set(parametros) == claves
    assert NIVELES["facil"]["entradas"] < NIVELES["experto"]["entradas"]
    assert NIVELES["facil"]["animacion"] > NIVELES["experto"]["animacion"]
    for parametros in NIVELES.values():
        assert parametros["entradas"] * parametros["intervalo"] <= parametros["movimiento"]

def probar_seleccion_exige_dos_casillas_distintas():
    seleccion = SelectionManager()
    assert seleccion.registrar(3) is True
    assert seleccion.registrar(3) is False
    assert seleccion.registrar(9) is True
    assert seleccion.registrar(1) is False
    assert seleccion.seleccionadas() == (3, 9)
    assert seleccion.completa() is True

def probar_puntaje_y_generador_son_deterministas():
    assert ScoreManager.evaluar((3, 9), {"h1": 3, "h2": 7}) == {
        "aciertos": 1, "errores": 1, "precision": 50.0,
    }
    a = GameManager.generar("normal", semilla=42)
    b = GameManager.generar("normal", semilla=42)
    assert a == b
    assert RONDAS_RASTREO == 6
    assert len(a["observacion"]) == 12
    assert len(a["movimientos"]) == NIVELES["normal"]["entradas"]
    assert set(a["final"]) == {"h1", "h2"}
    assert len(set(a["final"].values())) == 2
    assert all(m["lado"] in LADOS for m in a["movimientos"])

def probar_rastreo_registrado_como_13a_prueba():
    assert "rastreo" not in JUEGOS_MINI
    assert JUEGOS_FIESTA[-2] == "rastreo"
    assert JUEGOS_FIESTA[-1] == "ppt"
    assert NOMBRES_JUEGOS["rastreo"] == "RASTREO DE HÁMSTERS"

def probar_rastreo_contrato_cliente():
    html = (BASE / "static/index.html").read_text(encoding="utf-8")
    js = (BASE / "static/app.js").read_text(encoding="utf-8")
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    assert 'data-juego="rastreo"' in html
    assert '"rastreo"' in js
    assert ".rastreo-tablero" in css
    assert "@keyframes rastreo-entrada" in css

def probar_rastreo_cliente_reutiliza_sprite_y_fases():
    js = (BASE / "static/app.js").read_text(encoding="utf-8")
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    assert "HAMSTER_PIXELES" in js and "AVE_SVG" in js
    assert "PELAJES[0]" in js
    assert "rastreo_hide" in js and "rastreo_result" in js
    assert "rastreo_answer" in js and "rastreo_move" in js
    assert "AnimationController" in js
    assert ".rastreo-casilla" in css
    assert "calc(-100% - var(--v-1))" in css and "calc(100% + var(--v-1))" in css

import asyncio, json, threading, time
from pathlib import Path
import uvicorn, websockets
import servidor
from arbitro import nucleo
from juego.rastreo import NIVELES, LADOS

async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)

nucleo.pausa = pausa_corta
config = uvicorn.Config(servidor.app, host="127.0.0.1", port=8786, log_level="error")
servidor_uvicorn = uvicorn.Server(config)
threading.Thread(target=servidor_uvicorn.run, daemon=True).start()
while not servidor_uvicorn.started:
    time.sleep(0.02)
URL = "ws://127.0.0.1:8786/ws"
BASE = Path(__file__).parent


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


async def probar_rastreo_individual_y_seleccion_invalida():
    cliente = Cliente(await websockets.connect(URL))
    await cliente.enviar({"type": "individual", "nombre": "RASTREO", "juegos": ["rastreo"]})
    await cliente.esperar("room_created")
    show = await cliente.esperar("rastreo_show")
    assert len(show["tablero"]) == 12
    assert "final" not in show and "h1" not in show
    await cliente.esperar("rastreo_hide")
    await cliente.esperar("rastreo_write")
    movimientos = cliente.de_tipo("rastreo_move")
    assert len(movimientos) == NIVELES["facil"]["entradas"]
    await cliente.enviar({"type": "rastreo_answer", "ronda": show["ronda"], "respuesta": [3]})
    await cliente.enviar({"type": "rastreo_answer", "ronda": show["ronda"], "respuesta": [3, 3]})
    await cliente.enviar({"type": "rastreo_answer", "ronda": show["ronda"], "respuesta": [3, 99]})
    assert not cliente.de_tipo("rastreo_feedback")
    await cliente.enviar({"type": "rastreo_answer", "ronda": show["ronda"], "respuesta": [0, 1]})
    await cliente.esperar("rastreo_feedback")
    assert len(cliente.de_tipo("rastreo_feedback")) == 1
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)


async def probar_rastreo_movimientos_secuenciales():
    cliente = Cliente(await websockets.connect(URL))
    await cliente.enviar({"type": "individual", "nombre": "SEC", "juegos": ["rastreo"]})
    await cliente.esperar("rastreo_show")
    await cliente.esperar("rastreo_write")
    movimientos = cliente.de_tipo("rastreo_move")
    assert [m["indice"] for m in movimientos] == list(range(1, len(movimientos) + 1))
    assert all(m["duracion"] > 0 and m["lado"] in LADOS for m in movimientos)
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)


async def probar_rastreo_fiesta_mandos_sin_posiciones():
    host = Cliente(await websockets.connect(URL))
    await host.enviar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]
    mando = Cliente(await websockets.connect(URL))
    await mando.enviar({"type": "join", "nombre": "Ana", "codigo": codigo})
    await mando.esperar("room_joined")
    await host.enviar({
        "type": "start", "juegos": ["rastreo"],
        "ajustes": {"rastreo": {"rondas": 1, "dificultad": "experto"}},
    })
    await host.esperar("rastreo_show")
    await mando.esperar("rastreo_show")
    await mando.esperar("rastreo_write")
    for mensaje in mando.recibidos:
        if mensaje["type"].startswith("rastreo_"):
            assert "tablero" not in mensaje and "final" not in mensaje
            assert "h1" not in mensaje and "h2" not in mensaje
    for cliente in (host, mando):
        await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)


async def main():
    probar_tablero_arranca_con_10_gatos_y_2_hamsters()
    probar_desplazamientos_en_los_cuatro_lados()
    probar_rastreo_no_duplica_ni_pierde_hamsters_tras_200_entradas()
    probar_cuatro_niveles_con_parametros_independientes()
    probar_seleccion_exige_dos_casillas_distintas()
    probar_puntaje_y_generador_son_deterministas()
    probar_rastreo_registrado_como_13a_prueba()
    probar_rastreo_contrato_cliente()
    probar_rastreo_cliente_reutiliza_sprite_y_fases()
    await probar_rastreo_individual_y_seleccion_invalida()
    await probar_rastreo_movimientos_secuenciales()
    await probar_rastreo_fiesta_mandos_sin_posiciones()
    print("\nOK - Rastreo de hamsters correcto")

if __name__ == "__main__":
    asyncio.run(main())
