"""Pruebas de integración de los siete minijuegos de Konitive.

Se juega cada prueba en INDIVIDUAL respondiendo siempre bien (así se comprueba
el cálculo del Brain Age y la precisión) y se hace una FIESTA con dos mandos
para verificar que la pantalla no puntúa y que los secretos no se filtran.

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
from juego.minijuegos import (
    JUEGOS_MINI,
    NOMBRES_MINI,
    RONDAS_MINI,
    cargar_frases,
    vuelto_optimo,
)


class ReconocedorFalso:
    def reconocer(self, trazos):
        x = trazos[0][0][0]
        indice = max(0, min(9, round(x * 10) - 1))
        return str(indice), 0.99, [0.0] * 10


servidor.reconocedor_digitos = ReconocedorFalso()


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


servidor.pausa = pausa_corta

config = uvicorn.Config(servidor.app, host="127.0.0.1", port=8770, log_level="error")
servidor_uvicorn = uvicorn.Server(config)
threading.Thread(target=servidor_uvicorn.run, daemon=True).start()
while not servidor_uvicorn.started:
    time.sleep(0.02)

URL = "ws://127.0.0.1:8770/ws"
TOTALES_SILABAS = {f["frase"]: len(f["silabas"]) for f in cargar_frases()}
ESCRITURA = ("triangulos",)


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
        frase = show["frase"]
        await cliente.enviar(
            {"type": "silabas_answer", "ronda": ronda, "respuesta": TOTALES_SILABAS[frase]}
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
    respondidas = 0
    fin = time.monotonic() + 30
    while time.monotonic() < fin and not host.de_tipo(f"{juego}_over"):
        for indice, msg in enumerate(host.recibidos):
            tipo = msg["type"]
            if indice < vistos.get(tipo, 0):
                continue
            vistos[tipo] = indice + 1
            if tipo == f"{juego}_show" and juego == "memoria":
                posiciones = msg["posiciones"]
        numero = len(host.de_tipo(f"{juego}_write"))
        if numero > respondidas and all(
            len(m.de_tipo(f"{juego}_write")) >= numero for m in mandos
        ):
            write = host.de_tipo(f"{juego}_write")[numero - 1]
            for mando in mandos:
                await responder(mando, juego, {}, write, posiciones)
            respondidas = numero
        await asyncio.sleep(0.01)

    assert host.de_tipo(f"{juego}_over"), f"No terminó la fiesta de {juego}"
    for mando in mandos:
        shows = mando.de_tipo(f"{juego}_show")
        assert len(shows) == RONDAS_MINI[juego], (juego, len(shows))
        for show in shows:
            if juego == "memoria":
                assert show["mira"] is True and "posiciones" not in show, show
            else:
                assert "mira" not in show, show
                secretos = ("vuelto", "optimo", "correcta", "orden", "resultado")
                assert not any(c in show for c in secretos), show

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


async def main() -> None:
    print("Individual:")
    for juego in JUEGOS_MINI:
        await jugar_individual(juego)
    print("Fiesta:")
    await jugar_fiesta("memoria")
    await jugar_fiesta("vuelto")
    await asyncio.sleep(0.1)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("\nOK - Siete minijuegos correctos en individual y fiesta")


if __name__ == "__main__":
    asyncio.run(main())
