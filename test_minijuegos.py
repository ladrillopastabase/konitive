"""Pruebas de integración de los ocho minijuegos de Konitive.

Se juega cada prueba en INDIVIDUAL respondiendo siempre bien (así se comprueba
el cálculo del Brain Age y la precisión) y se hace una FIESTA con dos mandos
para verificar que la pantalla no puntúa, conserva el estímulo grande (salvo
Stroop, que se borra) y los secretos no se filtran a los celulares.

Los reconocedores se parchean para «escribir» cifras y las pausas se acortan,
como en el resto de las pruebas del proyecto.
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
from arbitro.minijuegos import brain_age_y_puntos, exposicion_stroop
from juego.minijuegos import (
    JUEGOS_MINI,
    NOMBRES_MINI,
    RONDAS_MINI,
    cargar_frases,
    mana_para,
    vuelto_optimo,
)


class ReconocedorFalso:
    def reconocer(self, trazos):
        x = trazos[0][0][0]
        indice = max(0, min(9, round(x * 10) - 1))
        return str(indice), 0.99, [0.0] * 10


nucleo.reconocedor_digitos = ReconocedorFalso()


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


nucleo.pausa = pausa_corta

config = uvicorn.Config(servidor.app, host="127.0.0.1", port=8770, log_level="error")
servidor_uvicorn = uvicorn.Server(config)
threading.Thread(target=servidor_uvicorn.run, daemon=True).start()
while not servidor_uvicorn.started:
    time.sleep(0.02)

URL = "ws://127.0.0.1:8770/ws"
TOTALES_SILABAS = {f["frase"]: len(f["silabas"]) for f in cargar_frases()}
ESCRITURA = ("triangulos",)
SOLO_PANTALLA = ("stroop", "triangulos", "relojes", "vuelto", "silabas")
VISUAL_MINI = {
    "stroop": ("palabra", "tinta"),
    "triangulos": ("top", "ops", "op_final"),
    "relojes": ("reloj1", "reloj2", "periodo1", "periodo2"),
    "vuelto": ("producto", "precio_texto", "pago_texto"),
    "silabas": ("frase",),
}


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


def codigo_digito(digito: int) -> list:
    x = (digito + 1) / 10
    return [[[x, 0.2], [x, 0.8]]]


async def escribir(cliente, juego: str, numero: str, ronda: int) -> None:
    for indice, digito in enumerate(numero):
        await cliente.enviar(
            {
                "type": f"{juego}_digit",
                "ronda": ronda,
                "index": indice,
                "trazos": codigo_digito(int(digito)),
            }
        )


def resultado_triangulo(reto: dict) -> str:
    a, b, c = reto["top"]
    o1, o2 = reto["ops"]
    i1 = a + b if o1 == "+" else a - b
    i2 = b + c if o2 == "+" else b - c
    final = i1 + i2 if reto["op_final"] == "+" else i1 - i2
    return f"{final:02d}"


def diferencia_reloj(reloj1: list, reloj2: list) -> str:
    inicio = ((reloj1[0] - 1) % 12) * 60 + reloj1[1]
    final = ((reloj2[0] - 1) % 12) * 60 + reloj2[1]
    minutos = final - inicio
    if minutos < 0:
        minutos += 12 * 60
    return f"{minutos // 60:02d}{minutos % 60:02d}"


def monto(texto: str) -> int:
    return int(texto.replace("$", "").replace(".", ""))


async def responder(cliente, juego: str, show: dict, write: dict, posiciones: dict) -> None:
    ronda = write["ronda"]
    if juego == "stroop":
        await cliente.enviar(
            {"type": "stroop_answer", "ronda": ronda, "respuesta": show["tinta"]}
        )
    elif juego == "triangulos":
        await escribir(cliente, juego, resultado_triangulo(write["estimulo"]), ronda)
    elif juego == "relojes":
        estimulo = show
        diff = diferencia_reloj(estimulo["reloj1"], estimulo["reloj2"])
        await cliente.enviar(
            {
                "type": "relojes_answer",
                "ronda": ronda,
                "respuesta": {"horas": int(diff[:2]), "minutos": int(diff[2:])},
            }
        )
    elif juego == "menor":
        orden = [
            i for i, _ in sorted(enumerate(write["numeros"]), key=lambda par: par[1]["valor"])
        ]
        for indice in orden:
            await cliente.enviar(
                {"type": "menor_answer", "ronda": ronda, "respuesta": indice}
            )
    elif juego == "memoria":
        for numero in range(1, write["cantidad"] + 1):
            await cliente.enviar(
                {
                    "type": "memoria_answer",
                    "ronda": ronda,
                    "respuesta": posiciones[str(numero)],
                }
            )
    elif juego == "vuelto":
        vuelto = monto(write["pago_texto"]) - monto(write["precio_texto"])
        await cliente.enviar(
            {"type": "vuelto_answer", "ronda": ronda, "respuesta": vuelto_optimo(vuelto)}
        )
    elif juego == "silabas":
        # La pantalla de respuesta debe traer la frase (antes llegaba vacía).
        frase = write["frase"]
        assert not show or frase == show["frase"], (write, show)
        await cliente.enviar(
            {"type": "silabas_answer", "ronda": ronda, "respuesta": TOTALES_SILABAS[frase]}
        )
    elif juego == "ppt":
        await cliente.enviar(
            {
                "type": "ppt_answer",
                "ronda": write["ronda"],
                "respuesta": mana_para(show["rival"], show["objetivo"]),
            }
        )


async def jugar_individual(juego: str) -> None:
    ws = await websockets.connect(URL)
    cliente = Cliente(ws)
    await cliente.enviar({"type": "individual", "nombre": "Solo", "juegos": [juego]})
    bienvenida = await cliente.esperar("room_created")
    assert bienvenida["juegos"] == [juego], bienvenida

    inicio = await cliente.esperar("individual_game_start")
    assert inicio["juego"] == juego, inicio
    assert inicio["nombre_juego"] == NOMBRES_MINI[juego], inicio

    vistos: dict[str, int] = {}
    ultimo_show: dict = {}
    posiciones: dict = {}
    fin = time.monotonic() + 30
    while time.monotonic() < fin:
        for indice, msg in enumerate(cliente.recibidos):
            tipo = msg["type"]
            if indice < vistos.get(tipo, 0):
                continue
            vistos[tipo] = indice + 1
            if tipo == f"{juego}_show":
                ultimo_show = msg
                if juego == "memoria":
                    posiciones = msg["posiciones"]
                    assert posiciones and "esperado" not in msg, msg
                if juego == "stroop":
                    assert "correcta" not in msg, msg
                if juego == "menor":
                    assert "orden" not in msg, msg
                if juego == "vuelto":
                    assert "vuelto" not in msg and "optimo" not in msg, msg
            elif tipo == f"{juego}_write":
                if juego in ESCRITURA:
                    estimulo = msg["estimulo"]
                    secretos = ("resultado", "intermedios", "esperado", "total", "silabas")
                    assert not any(c in estimulo for c in secretos), estimulo
                await responder(cliente, juego, ultimo_show, msg, posiciones)
            elif tipo == f"{juego}_write" and juego == "relojes":
                await responder(cliente, juego, ultimo_show, {}, posiciones)
        if cliente.de_tipo("individual_summary"):
            break
        await asyncio.sleep(0.01)

    resumen = await cliente.esperar("individual_summary")
    dato = resumen["resumen"][juego]
    assert dato["precision"] == 100 and dato["aciertos"] == RONDAS_MINI[juego], dato
    assert dato["rondas"] == RONDAS_MINI[juego] and dato["errores"] == 0, dato
    assert dato["brain_age"] >= 0 and dato["tiempo_promedio"] >= 0, dato
    assert resumen["orden"] == [juego], resumen
    assert not cliente.de_tipo(f"{juego}_over"), "INDIVIDUAL no debe enviar cierre de juego"

    resultados = cliente.de_tipo(f"{juego}_result")
    assert len(resultados) == RONDAS_MINI[juego], (juego, len(resultados))
    assert all(r["acierto"] is True for r in resultados), juego
    if juego in ESCRITURA:
        comentarios = cliente.de_tipo(f"{juego}_feedback")
        assert len(comentarios) >= RONDAS_MINI[juego], (juego, len(comentarios))
        assert all(c["aceptada"] and c["acepta"] for c in comentarios), juego

    if juego == "stroop":
        shows = cliente.de_tipo("stroop_show")
        hides = cliente.de_tipo("stroop_hide")
        assert len(shows) == len(hides) == RONDAS_MINI["stroop"], (len(shows), len(hides))
        duraciones = [show["duracion"] for show in shows]
        assert duraciones[0] == exposicion_stroop(1), duraciones
        assert duraciones[-1] == exposicion_stroop(RONDAS_MINI["stroop"]), duraciones
        assert all(a >= b for a, b in zip(duraciones, duraciones[1:])), duraciones
        assert all("palabra" in show and "tinta" in show for show in shows), shows
        writes = cliente.de_tipo("stroop_write")
        assert all("palabra" not in w and "tinta" not in w for w in writes), writes

    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
    print(f"  {NOMBRES_MINI[juego]}: {RONDAS_MINI[juego]} rondas correctas, Brain Age {dato['brain_age']}")


async def jugar_fiesta(juego: str) -> None:
    ws = await websockets.connect(URL)
    host = Cliente(ws)
    await host.enviar({"type": "fiesta", "nombre": "Pantalla"})
    bienvenida = await host.esperar("room_created")
    codigo = bienvenida["codigo"]
    host_id = bienvenida["id"]

    mandos = []
    ids_mandos = set()
    for nombre in ("Ana", "Beto"):
        mws = await websockets.connect(URL)
        mando = Cliente(mws)
        await mando.enviar({"type": "join", "nombre": nombre, "codigo": codigo})
        unido = await mando.esperar("room_joined")
        assert unido["rol"] == "mando", unido
        mandos.append(mando)
        ids_mandos.add(unido["id"])

    await host.enviar({"type": "start", "juego": juego})
    vistos: dict[str, int] = {}
    posiciones: dict = {}
    shows: dict[str, dict] = {}
    respondidas = 0
    fin = time.monotonic() + 30
    while time.monotonic() < fin and not host.de_tipo(f"{juego}_over"):
        for indice, msg in enumerate(host.recibidos):
            tipo = msg["type"]
            if indice < vistos.get(tipo, 0):
                continue
            vistos[tipo] = indice + 1
            if tipo == f"{juego}_show":
                shows[juego] = msg
                if juego == "memoria":
                    posiciones = msg["posiciones"]
        numero = len(host.de_tipo(f"{juego}_write"))
        if numero > respondidas and all(
            len(m.de_tipo(f"{juego}_write")) >= numero for m in mandos
        ):
            write = host.de_tipo(f"{juego}_write")[numero - 1]
            if juego in SOLO_PANTALLA:
                if juego == "stroop":
                    # La palabra se borró con el _hide: no se reenvía al responder.
                    assert not any(c in write for c in VISUAL_MINI[juego]), write
                else:
                    for clave in VISUAL_MINI[juego]:
                        assert clave in write, (juego, clave, write)
            for mando in mandos:
                await responder(mando, juego, shows.get(juego, {}), write, posiciones)
            respondidas = numero
        await asyncio.sleep(0.01)

    assert host.de_tipo(f"{juego}_over"), f"No terminó la fiesta de {juego}"
    if juego == "stroop":
        hides = host.de_tipo("stroop_hide")
        assert len(hides) == nucleo.RONDAS_FIESTA, len(hides)
        assert all("duracion" in show for show in host.de_tipo("stroop_show"))
        for mando in mandos:
            assert len(mando.de_tipo("stroop_hide")) == nucleo.RONDAS_FIESTA
    for mando in mandos:
        shows_mando = mando.de_tipo(f"{juego}_show")
        assert len(shows_mando) == nucleo.RONDAS_FIESTA, (juego, len(shows_mando))
        for show in shows_mando:
            if juego in SOLO_PANTALLA or juego == "memoria":
                assert show["mira"] is True, show
                claves = VISUAL_MINI.get(juego, ()) + (
                    ("posiciones", "grilla") if juego == "memoria" else ()
                )
                assert not any(c in show for c in claves), show
            else:
                assert "mira" not in show, show
                secretos = ("vuelto", "optimo", "correcta", "orden", "resultado")
                assert not any(c in show for c in secretos), show
        writes_mando = mando.de_tipo(f"{juego}_write")
        assert len(writes_mando) == nucleo.RONDAS_FIESTA, (juego, len(writes_mando))
        for write in writes_mando:
            if juego in SOLO_PANTALLA:
                prohibidas = VISUAL_MINI[juego] + ("estimulo",)
                assert not any(c in write for c in prohibidas), write
        # El informe de la ronda se ve solo en la pantalla: el celular no
        # recibe la respuesta correcta ni el desglose.
        resultados_mando = mando.de_tipo(f"{juego}_result")
        assert len(resultados_mando) == nucleo.RONDAS_FIESTA, (juego, len(resultados_mando))
        for resultado in resultados_mando:
            assert not any(
                c in resultado for c in ("reto", "jugadores", "clasificacion", "acierto")
            ), resultado

    resultados_pantalla = host.de_tipo(f"{juego}_result")
    assert len(resultados_pantalla) == nucleo.RONDAS_FIESTA, (juego, len(resultados_pantalla))
    assert all("reto" in r for r in resultados_pantalla), resultados_pantalla

    podio = await host.esperar("podium_update")
    assert host_id not in podio["puntos_juego"], podio
    assert set(podio["puntos_juego"]) == ids_mandos, podio
    await host.esperar("back_to_selector")
    for mando in mandos:
        await mando.esperar("back_to_selector")
        await mando.cerrar()
    await host.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
    print(f"  Fiesta {NOMBRES_MINI[juego]}: mandos responden, pantalla no puntúa, sin secretos")


async def jugar_lista_fiesta() -> None:
    """Lista elegida en el lobby: rondas y dificultad por juego, podio entre juegos."""
    lista = ["vuelto", "silabas"]
    ajustes = {"vuelto": {"rondas": 2, "dificultad": "dificil"}, "silabas": {"rondas": 3}}
    host = Cliente(await websockets.connect(URL))
    await host.enviar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]
    mandos = []
    for nombre in ("Ana", "Beto"):
        mando = Cliente(await websockets.connect(URL))
        await mando.enviar({"type": "join", "nombre": nombre, "codigo": codigo})
        await mando.esperar("room_joined")
        mandos.append(mando)

    await host.enviar({"type": "start", "juegos": lista, "ajustes": ajustes})
    respondidas = {juego: 0 for juego in lista}
    shows: dict[str, dict] = {}
    fin = time.monotonic() + 60
    while time.monotonic() < fin and not host.de_tipo("back_to_selector"):
        for msg in host.recibidos:
            for juego in lista:
                if msg["type"] == f"{juego}_show":
                    shows[juego] = msg
        for juego in lista:
            numero = len(host.de_tipo(f"{juego}_write"))
            if numero > respondidas[juego] and all(
                len(m.de_tipo(f"{juego}_write")) >= numero for m in mandos
            ):
                write = host.de_tipo(f"{juego}_write")[numero - 1]
                for mando in mandos:
                    await responder(mando, juego, shows.get(juego, {}), write, {})
                respondidas[juego] = numero
        await asyncio.sleep(0.01)

    assert host.de_tipo("back_to_selector"), "La lista de fiesta no terminó"
    assert len(host.de_tipo("vuelto_show")) == 2, len(host.de_tipo("vuelto_show"))
    assert len(host.de_tipo("silabas_show")) == 3, len(host.de_tipo("silabas_show"))
    assert all(s["dificultad"] == "DIFÍCIL" for s in host.de_tipo("vuelto_show"))
    assert [s["ronda"] for s in host.de_tipo("vuelto_show")] == [1, 2]
    podios = host.de_tipo("podium_update")
    assert [p["siguiente"] for p in podios] == [NOMBRES_MINI["silabas"], ""], podios
    assert len(host.de_tipo("back_to_selector")) == 1  # solo al acabar la lista
    for mando in mandos:
        await mando.cerrar()
    await host.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
    print("  Fiesta con lista: rondas y dificultad por juego, podio entre juegos")


async def main() -> None:
    assert brain_age_y_puntos(10.0, 0) == (10.0, 900)
    assert brain_age_y_puntos(10.0, 2) == (20.0, 800), "5 s por error"
    print("Individual:")
    for juego in JUEGOS_MINI:
        await jugar_individual(juego)
    print("Fiesta:")
    for juego in ("memoria",) + SOLO_PANTALLA:
        await jugar_fiesta(juego)
    await jugar_lista_fiesta()
    await asyncio.sleep(0.1)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("\nOK - Ocho minijuegos correctos en individual y fiesta")


if __name__ == "__main__":
    asyncio.run(main())
