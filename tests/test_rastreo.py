from apoyo import RAIZ, Cliente, cliente_js, levantar_servidor  # primero: deja la raíz del proyecto en sys.path
import random

from juego.minijuegos import JUEGOS_MINI
from arbitro.nucleo import JUEGOS_FIESTA, NOMBRES_JUEGOS
from juego.catalogo import POR_ID
from juego.rastreo import (
    CELDAS, HAMSTERS, LADOS, NIVELES, RONDAS_RASTREO,
    BoardManager, CatSpawner, DifficultyManager, GameManager,
    HamsterManager, MovementSystem, ScoreManager, SelectionManager,
)

BASE = RAIZ

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

def probar_hamster_no_reaparece_en_casilla_que_dejo_el_otro():
    casos = 0
    for semilla in range(200):
        rng = random.Random(semilla)
        tablero, hamsters = BoardManager(rng), HamsterManager(rng)
        tablero.inicializar()
        sistema, spawner = MovementSystem(tablero, hamsters), CatSpawner(rng)
        for _ in range(12):
            antes = hamsters.posiciones(tablero)
            lado, linea = spawner.siguiente()
            resultado = sistema.aplicar(lado, linea)
            if resultado["reaparecio"] is None:
                continue
            casos += 1
            despues = hamsters.posiciones(tablero)
            vuelve = next(h for h in HAMSTERS if despues.get(h) == resultado["reaparecio"])
            otro = next(h for h in HAMSTERS if h != vuelve)
            assert resultado["reaparecio"] != antes[otro], (
                f"semilla {semilla}: reapareció en {resultado['reaparecio']}, "
                f"la casilla que {otro} acababa de dejar"
            )
    assert casos > 0

def probar_cuatro_niveles_con_parametros_independientes():
    assert tuple(NIVELES) == ("facil", "normal", "dificil", "experto")
    claves = {"observacion", "movimiento", "entradas", "intervalo", "animacion"}
    for parametros in NIVELES.values():
        assert set(parametros) == claves
    assert NIVELES["facil"]["entradas"] < NIVELES["experto"]["entradas"]
    assert NIVELES["facil"]["animacion"] > NIVELES["experto"]["animacion"]
    for parametros in NIVELES.values():
        assert parametros["entradas"] * parametros["intervalo"] <= parametros["movimiento"]

def probar_nivel_para_ronda_escala_y_top():
    from juego.rastreo import nivel_para_ronda
    assert [nivel_para_ronda("facil", r) for r in range(1, 7)] == [
        "facil", "normal", "dificil", "experto", "experto", "experto",
    ]
    assert [nivel_para_ronda("normal", r) for r in range(1, 5)] == [
        "normal", "dificil", "experto", "experto",
    ]
    assert nivel_para_ronda("experto", 10) == "experto"
    assert nivel_para_ronda("desconocido", 3) == "dificil"
    assert nivel_para_ronda("facil", 0) == "facil"

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
    js = cliente_js()
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    assert POR_ID["rastreo"]["dificultades"][-1] == "experto"
    assert (BASE / "static/juegos/rastreo.js").exists()
    assert "rastreo_countdown:" in js
    assert ".rastreo-tablero" in css
    assert "@keyframes rastreo-entrada" in css

def probar_rastreo_cliente_reutiliza_sprite_y_fases():
    js = cliente_js()
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    assert "HAMSTER_PIXELES" in js and "AVE_SVG" in js
    assert "PELAJES[0]" in js
    assert "rastreo_hide" in js and "rastreo_result" in js
    assert "rastreo_answer" in js and "rastreo_move" in js
    assert "AnimationController" in js
    assert ".rastreo-casilla" in css
    assert "calc(-100% - var(--v-1))" in css and "calc(100% + var(--v-1))" in css

def probar_rastreo_deslizamiento_suave_de_linea():
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    bloque = css[css.index("/* Un paso exacto de casilla"):css.index("/* Triángulos:")]
    assert "steps(1, end)" not in bloque
    assert "cubic-bezier(0.16, 1, 0.3, 1)" in bloque
    assert "var(--rastreo-duracion" in bloque
    assert "outline: 3px solid var(--rosa-borde)" in bloque
    for lado in ("izquierda", "derecha", "arriba", "abajo"):
        assert f"animation-name: rastreo-entrada-{lado};" in bloque
    assert "@keyframes rastreo-aviso-reducido" in bloque
    media = css.split("@media (prefers-reduced-motion: reduce)", 1)[1].split("@media", 1)[0]
    assert "rastreo-aviso-reducido" in media

def probar_rastreo_salida_y_reaparicion_en_el_plan():
    plan = GameManager.generar("normal", semilla=3)
    movimientos = plan["movimientos"]
    assert any(m["reaparecio"] is not None for m in movimientos)
    for movimiento in movimientos:
        assert set(movimiento) == {"lado", "linea", "duracion", "salida", "reaparecio"}
        assert 0 <= movimiento["salida"] < CELDAS
        assert movimiento["reaparecio"] is None or 0 <= movimiento["reaparecio"] < CELDAS
        assert "h1" not in movimiento and "h2" not in movimiento
    primero = next(m for m in movimientos if m["reaparecio"] is not None)
    assert (primero["lado"], primero["linea"], primero["salida"], primero["reaparecio"]) == (
        "abajo", 2, 2, 9,
    )

def probar_rastreo_cliente_animacion_salida_y_reaparicion():
    js = cliente_js()
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    codigo = (BASE / "arbitro/rastreo.py").read_text(encoding="utf-8")
    assert ".rastreo-hamster" in css and "pointer-events: none" in css
    tablero_css = css[css.index(".rastreo-tablero {"):css.index(".rastreo-casilla {")]
    assert "position: relative" in tablero_css
    assert "movimiento.salida" in js and "movimiento.reaparecio" in js
    assert "sprite.animate(" in js
    assert "prefers-reduced-motion" in js
    assert '"salida": movimiento["salida"]' in codigo
    assert '"reaparecio": movimiento["reaparecio"]' in codigo

def probar_rastreo_cliente_muestra_nivel():
    js = cliente_js()
    inicio = js.index("rastreo_countdown:")
    bloque = js[inicio:js.index("}),", inicio)]
    assert "msg.dificultad" in bloque
    inicio = js.index("function mostrarRastreo(msg, fase)")
    bloque = js[inicio:js.index("function configurarSeleccionRastreo", inicio)]
    assert "msg.dificultad" in bloque
    assert "FASES_RASTREO[fase]" in bloque

def probar_resumen_individual_rastreo_y_final_sin_ids():
    js = cliente_js()
    codigo = (BASE / "arbitro/rastreo.py").read_text(encoding="utf-8")
    inicio = js.index("function mostrarResumenIndividual")
    bloque = js[inicio : js.index("\n}", inicio)]
    assert "nombreJuego(clave)" in bloque
    detalle = bloque.split("const detalle =", 1)[1].split("return `<div", 1)[0]
    assert 'clave in MINIJUEGOS || clave === "rastreo"' in detalle
    assert "PRECISIÓN ${dato.precision ?? 0}% · BRAIN AGE ${dato.brain_age ?? 0}" in detalle
    assert "VICTORIAS ${dato.victorias ?? 0} · RONDAS ${dato.rondas ?? 0}" in detalle
    assert '"final": list(plan["final"].values())' in codigo
    assert '"final": dict(plan["final"])' not in codigo

def probar_documentacion_incluye_rastreo():
    readme = (BASE / "README.md").read_text(encoding="utf-8")
    producto = (BASE / "PRODUCT.md").read_text(encoding="utf-8")
    assert "RASTREO DE HÁMSTERS" in readme
    assert "13 pruebas" in readme or "las 13" in readme
    assert "nueve minijuegos" in readme
    assert "python tests/test_rastreo.py" in readme
    assert "RASTREO DE HÁMSTERS" in producto

import asyncio, json, threading, time
import uvicorn, websockets
import servidor
from arbitro import nucleo
from arbitro import rastreo as arbitro_rastreo

async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)

nucleo.pausa = pausa_corta
arbitro_rastreo.TIEMPO_IDENTIFICACION = 1.0
URL = levantar_servidor()


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
    host_movimientos = host.de_tipo("rastreo_move")
    mando_movimientos = mando.de_tipo("rastreo_move")
    assert host_movimientos and len(host_movimientos) == len(mando_movimientos)
    assert all("salida" in m and "reaparecio" in m for m in host_movimientos)
    assert all("salida" not in m and "reaparecio" not in m for m in mando_movimientos)
    for mensaje in mando.recibidos:
        if mensaje["type"].startswith("rastreo_"):
            assert "tablero" not in mensaje and "final" not in mensaje
            assert "h1" not in mensaje and "h2" not in mensaje
    for cliente in (host, mando):
        await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)


async def probar_rastreo_dificultad_sube_por_ronda():
    cliente = Cliente(await websockets.connect(URL))
    await cliente.enviar({"type": "individual", "nombre": "SUBE", "juegos": ["rastreo"]})
    await cliente.esperar("rastreo_show")
    while len(cliente.de_tipo("rastreo_result")) < RONDAS_RASTREO:
        await asyncio.sleep(0.01)
    assert [m["dificultad"] for m in cliente.de_tipo("rastreo_countdown")] == [
        "facil", "normal", "dificil", "experto", "experto", "experto",
    ]
    por_ronda = {}
    for m in cliente.de_tipo("rastreo_move"):
        por_ronda.setdefault(m["ronda"], []).append(m)
    assert [len(por_ronda[r]) for r in range(1, RONDAS_RASTREO + 1)] == [
        NIVELES[n]["entradas"] for n in
        ("facil", "normal", "dificil", "experto", "experto", "experto")
    ]
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)


async def probar_rastreo_fiesta_escalera_desde_base():
    host = Cliente(await websockets.connect(URL))
    await host.enviar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]
    mando = Cliente(await websockets.connect(URL))
    await mando.enviar({"type": "join", "nombre": "Ana", "codigo": codigo})
    await mando.esperar("room_joined")
    await host.enviar({
        "type": "start", "juegos": ["rastreo"],
        "ajustes": {"rastreo": {"rondas": 4, "dificultad": "normal"}},
    })
    while len(host.de_tipo("rastreo_result")) < 4:
        await asyncio.sleep(0.01)
    assert [m["dificultad"] for m in host.de_tipo("rastreo_countdown")] == [
        "normal", "dificil", "experto", "experto",
    ]
    for mensaje in mando.recibidos:
        if mensaje["type"].startswith("rastreo_"):
            assert "tablero" not in mensaje and "final" not in mensaje
            assert "salida" not in mensaje and "reaparecio" not in mensaje
            assert "h1" not in mensaje and "h2" not in mensaje
    for cliente in (host, mando):
        await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)


async def main():
    probar_tablero_arranca_con_10_gatos_y_2_hamsters()
    probar_desplazamientos_en_los_cuatro_lados()
    probar_rastreo_no_duplica_ni_pierde_hamsters_tras_200_entradas()
    probar_hamster_no_reaparece_en_casilla_que_dejo_el_otro()
    probar_cuatro_niveles_con_parametros_independientes()
    probar_nivel_para_ronda_escala_y_top()
    probar_seleccion_exige_dos_casillas_distintas()
    probar_puntaje_y_generador_son_deterministas()
    probar_rastreo_registrado_como_13a_prueba()
    probar_rastreo_contrato_cliente()
    probar_rastreo_cliente_reutiliza_sprite_y_fases()
    probar_rastreo_deslizamiento_suave_de_linea()
    probar_rastreo_salida_y_reaparicion_en_el_plan()
    probar_rastreo_cliente_animacion_salida_y_reaparicion()
    probar_rastreo_cliente_muestra_nivel()
    probar_resumen_individual_rastreo_y_final_sin_ids()
    probar_documentacion_incluye_rastreo()
    await probar_rastreo_individual_y_seleccion_invalida()
    await probar_rastreo_movimientos_secuenciales()
    await probar_rastreo_fiesta_mandos_sin_posiciones()
    await probar_rastreo_dificultad_sube_por_ronda()
    await probar_rastreo_fiesta_escalera_desde_base()
    print("\nOK - Rastreo de hamsters correcto")

if __name__ == "__main__":
    asyncio.run(main())
