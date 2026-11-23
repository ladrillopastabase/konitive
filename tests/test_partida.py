"""Prueba del flujo completo con jugadores simulados.

Parchea el reconocedor (para poder "escribir" cualquier letra) y acorta las
pausas, pero ejercita el mismo código del servidor y el mismo protocolo
WebSocket.

Escenarios:

1. Victoria directa: un jugador gana los dos minijuegos.
2. Empate 1-1 y desempate al azar.
3. Modo práctica: un jugador solo, rondas continuas y salida limpia.

También valida las listas de palabras, los datos de salto de las aves, el
conteo en vivo y que el total de escritura coincida con su desglose.
"""
from __future__ import annotations

from apoyo import levantar_servidor  # primero: deja la raíz del proyecto en sys.path

import asyncio
import json
import re
import time

import websockets

import servidor
from arbitro import nucleo
from arbitro.puntuacion import puntuacion
from juego.palabras import LONGITUDES_POR_NIVEL, PALABRAS


class ReconocedorFalso:
    """Decodifica la letra esperada desde la x del primer punto del trazo."""

    def reconocer(self, trazos):
        x = trazos[0][0][0]
        indice = max(0, min(25, round(x * 27) - 1))
        return chr(65 + indice), 0.99, [0.0] * 26


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.03)


nucleo.reconocedor = ReconocedorFalso()
nucleo.pausa = pausa_corta

URL = levantar_servidor()


def codigo_letra(letra: str) -> list:
    x = (ord(letra) - 65 + 1) / 27
    return [[[x, 0.5], [x, 0.6]]]


def validar_palabras() -> None:
    assert LONGITUDES_POR_NIVEL == (3, 4, 5, 6, 7, 8, 8, 8)
    for idioma, niveles in PALABRAS.items():
        for largo, palabras in niveles.items():
            assert palabras, f"{idioma}/{largo} está vacío"
            for palabra in palabras:
                assert re.fullmatch(r"[A-Z]+", palabra), f"Palabra no A-Z: {palabra}"
                assert len(palabra) == largo, f"{palabra} no mide {largo}"
    print("Palabras: longitudes 3-8 y solo A-Z, correcto")


def validar_mensaje(msg: dict) -> None:
    """Comprobaciones que valen para todos los escenarios."""
    tipo = msg["type"]
    if tipo == "error":
        raise AssertionError(f"Error del servidor: {msg}")
    if tipo == "bird_tally":
        assert all(0 <= n <= 200 for n in msg["conteos"].values()), msg
        assert isinstance(msg["confirmados"], list), msg
    if tipo == "practice_summary":
        assert "ganador" not in msg, "El resumen de práctica no debe tener ganador"
        assert set(msg["resumen"]) == {"pajaros", "escritura"}, msg
        for dato in msg["resumen"].values():
            assert set(dato) == {
                "rondas", "victorias", "mejor",
                "tiempo_total", "errores", "puntuacion",
            }, dato
    if tipo == "birds_show":
        for ave in msg["aves"]:
            for clave in ("salta", "periodo", "fase", "duracion", "dx", "dy", "altura"):
                assert clave in ave, f"Falta el dato de salto {clave}"
        # Desde el nivel 1 hay saltitos, pero nunca saltan todos a la vez.
        assert not all(ave["salta"] for ave in msg["aves"]), "Nunca saltan todos"
    if tipo == "round_result" and msg["juego"] == "escritura":
        desglose = msg["desglose"]
        for pid, total in msg["puntuacion"].items():
            dato = desglose[pid]
            # `puntuacion` acumula las rondas previas; el tiempo de esta ronda no.
            calculado = puntuacion(dato["puntuacion"], 0)
            assert calculado == total, (dato, total)
            assert dato["puntuacion"] == total, (dato, total)
            assert (
                dato["correctas"] + dato["automaticas"] >= 0
            ), dato


async def jugador(
    nombre: str,
    codigo: str | None,
    cola: asyncio.Queue,
    ritmo_pajaros: float,
    ritmo_escritura: float,
    practica: bool = False,
    max_rondas: int | None = None,
    accion_resumen: str | None = None,
):
    async with websockets.connect(URL) as ws:
        if practica:
            await ws.send(json.dumps({"type": "practice", "nombre": nombre}))
        elif codigo is None:
            await ws.send(json.dumps({"type": "create", "nombre": nombre}))
        else:
            await ws.send(json.dumps({"type": "join", "nombre": nombre, "codigo": codigo}))

        conteo_pajaros = 0
        palabra = ""
        rondas = 0
        async for crudo in ws:
            msg = json.loads(crudo)
            await cola.put((nombre, msg))

            if msg["type"] == "error":
                raise AssertionError(f"{nombre}: {msg['mensaje']}")

            if msg["type"] == "player_joined" and codigo is None and not practica:
                await ws.send(json.dumps({"type": "start"}))

            if msg["type"] == "birds_show":
                conteo_pajaros = len(msg["aves"])

            elif msg["type"] == "birds_hide":
                await asyncio.sleep(ritmo_pajaros)
                # El jugador mueve el contador antes de confirmar.
                await ws.send(json.dumps({"type": "bird_tally", "count": conteo_pajaros}))
                await ws.send(json.dumps({"type": "bird_answer", "count": conteo_pajaros}))

            elif msg["type"] == "word_show":
                # El jugador "ve" la palabra durante el flash y la recuerda.
                palabra = msg["palabra"]

            elif msg["type"] == "word_write":
                for indice, letra in enumerate(palabra):
                    await ws.send(
                        json.dumps(
                            {
                                "type": "letter",
                                "index": indice,
                                "trazos": codigo_letra(letra),
                            }
                        )
                    )
                    await asyncio.sleep(ritmo_escritura)

            elif msg["type"] == "practice_summary":
                if accion_resumen == "continuar":
                    await asyncio.sleep(0.02)
                    await ws.send(json.dumps({"type": "continue_practice"}))
                else:
                    await ws.send(json.dumps({"type": "leave"}))
                    break

            elif msg["type"] == "round_result":
                rondas += 1
                if max_rondas and rondas >= max_rondas:
                    await ws.send(json.dumps({"type": "leave"}))
                    break


async def jugar_partida(
    titulo: str,
    ritmos_anfitrion: tuple[float, float],
    ritmos_invitado: tuple[float, float],
    esperar_desempate: bool,
) -> None:
    cola: asyncio.Queue = asyncio.Queue()
    anfitrion = asyncio.create_task(jugador("Ana", None, cola, *ritmos_anfitrion))

    _, bienvenida = await asyncio.wait_for(cola.get(), timeout=5)
    assert bienvenida["type"] == "room_created", bienvenida
    codigo = bienvenida["codigo"]
    invitado = asyncio.create_task(jugador("Beto", codigo, cola, *ritmos_invitado))

    vistos: dict[str, int] = {}
    ganador = None
    inicio = time.monotonic()

    try:
        while time.monotonic() - inicio < 90:
            try:
                _, msg = await asyncio.wait_for(cola.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            validar_mensaje(msg)
            tipo = msg["type"]
            vistos[tipo] = vistos.get(tipo, 0) + 1
            if tipo == "match_over":
                ganador = msg["ganador"]
                if vistos.get("match_over", 0) >= 2:
                    break
    finally:
        anfitrion.cancel()
        invitado.cancel()

    print(f"\n--- {titulo} ---")
    print("Mensajes:", json.dumps(vistos, indent=2, ensure_ascii=False))
    print("Ganador:", ganador)

    assert vistos.get("match_start", 0) == 2
    assert vistos.get("round_result", 0) >= 6
    assert vistos.get("bird_tally", 0) >= 2, "No se difundió el conteo en vivo"
    assert vistos.get("word_countdown", 0) >= 2, "Falta la cuenta previa de 3 s"
    assert vistos.get("word_countdown", 0) == vistos.get("word_show", 0)
    assert vistos.get("word_write", 0) >= 2, "No empezó la fase de escritura"
    assert vistos.get("word_hide", 0) == 0, "La palabra ya no se oculta con una cuenta posterior"
    # Cada anuncio llega a los dos jugadores: 2 minijuegos x 2 clientes.
    assert vistos.get("minigame_result", 0) == 4, "No se decidieron los dos minijuegos"
    assert vistos.get("match_over", 0) == 2, "No terminó para los dos jugadores"
    assert ganador is not None

    desempates = vistos.get("tiebreak_start", 0)
    if esperar_desempate:
        assert desempates == 2, "El empate 1-1 no disparó la ronda de desempate"
    else:
        assert desempates == 0, "No debía haber desempate"
    print("OK")


async def probar_practica() -> None:
    cola: asyncio.Queue = asyncio.Queue()
    tarea = asyncio.create_task(
        jugador("Solo", None, cola, 0.02, 0.01, practica=True, max_rondas=4)
    )

    vistos: dict[str, int] = {}
    inicio = time.monotonic()
    while time.monotonic() - inicio < 40 and not tarea.done():
        try:
            _, msg = await asyncio.wait_for(cola.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        validar_mensaje(msg)
        vistos[msg["type"]] = vistos.get(msg["type"], 0) + 1

    try:
        await asyncio.wait_for(tarea, timeout=3)
    finally:
        tarea.cancel()

    print("\n--- Modo práctica ---")
    print("Mensajes:", json.dumps(vistos, indent=2, ensure_ascii=False))

    assert vistos.get("match_start", 0) == 1
    assert vistos.get("round_result", 0) >= 4
    assert vistos.get("bird_tally", 0) >= 1
    assert vistos.get("word_countdown", 0) >= 1
    assert vistos.get("word_show", 0) >= 1
    assert vistos.get("word_write", 0) >= 1
    assert vistos.get("word_hide", 0) == 0
    assert vistos.get("match_over", 0) == 0, "La práctica no debe terminar"
    assert vistos.get("minigame_result", 0) == 0, "La práctica no decide minijuegos"
    # La salida se limpia: la sala desaparece.
    await asyncio.sleep(0.15)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("OK")


async def probar_resumen_practica() -> None:
    """Tras 3 victorias por juego se entrega un informe, no un 'ganador: nadie'."""
    cola: asyncio.Queue = asyncio.Queue()
    tarea = asyncio.create_task(
        jugador(
            "Solo",
            None,
            cola,
            0.02,
            0.01,
            practica=True,
            max_rondas=7,
            accion_resumen="continuar",
        )
    )

    vistos: dict[str, int] = {}
    resumen_recibido = None
    inicio = time.monotonic()
    while time.monotonic() - inicio < 60 and not tarea.done():
        try:
            _, msg = await asyncio.wait_for(cola.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        validar_mensaje(msg)
        vistos[msg["type"]] = vistos.get(msg["type"], 0) + 1
        if msg["type"] == "practice_summary":
            resumen_recibido = msg["resumen"]

    try:
        await asyncio.wait_for(tarea, timeout=3)
    finally:
        tarea.cancel()

    print("\n--- Resumen de práctica ---")
    print("Mensajes:", json.dumps(vistos, indent=2, ensure_ascii=False))
    print("Resumen:", json.dumps(resumen_recibido, indent=2, ensure_ascii=False))

    assert vistos.get("practice_summary", 0) == 1
    assert vistos.get("match_over", 0) == 0, "La práctica sigue sin final competitivo"
    assert vistos.get("round_result", 0) >= 7, "No se reanudó tras el resumen"
    assert resumen_recibido is not None
    assert resumen_recibido["pajaros"]["victorias"] == 3
    assert resumen_recibido["escritura"]["victorias"] == 3
    assert resumen_recibido["pajaros"]["rondas"] == 3
    assert resumen_recibido["escritura"]["rondas"] == 3
    await asyncio.sleep(0.15)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("OK")


async def main():
    validar_palabras()

    await jugar_partida(
        "Victoria directa",
        ritmos_anfitrion=(0.02, 0.01),
        ritmos_invitado=(0.09, 0.05),
        esperar_desempate=False,
    )

    await asyncio.sleep(0.3)
    await jugar_partida(
        "Empate 1-1 y desempate",
        ritmos_anfitrion=(0.02, 0.06),
        ritmos_invitado=(0.09, 0.01),
        esperar_desempate=True,
    )

    await asyncio.sleep(0.3)
    await probar_practica()

    await asyncio.sleep(0.3)
    await probar_resumen_practica()

    print("\nOK - Flujo completo correcto (todos los escenarios)")


if __name__ == "__main__":
    asyncio.run(main())
