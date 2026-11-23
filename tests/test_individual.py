"""Pruebas del modo INDIVIDUAL (uno, varios o todos los juegos).

Verifica que los juegos elegidos se jueguen en orden canónico, uno detrás de
otro, sin mensajes finales intermedios, y que al terminar se entregue un
resumen conjunto con el Brain Age de todas las pruebas.

Los reconocedores se parchean para poder «escribir» letras y cifras, y las
pausas se acortan, igual que en el resto de las pruebas.
"""
from __future__ import annotations

from apoyo import Cliente, levantar_servidor  # primero: deja la raíz del proyecto en sys.path

import asyncio
import json
import time

import websockets

import servidor
from arbitro import nucleo


class ReconocedorLetrasFalso:
    def reconocer(self, trazos):
        x = trazos[0][0][0]
        indice = max(0, min(25, round(x * 27) - 1))
        return chr(65 + indice), 0.99, [0.0] * 26


class ReconocedorDigitosFalso:
    def reconocer(self, trazos):
        x = trazos[0][0][0]
        indice = max(0, min(9, round(x * 10) - 1))
        return str(indice), 0.99, [0.0] * 10


nucleo.reconocedor = ReconocedorLetrasFalso()
nucleo.reconocedor_digitos = ReconocedorDigitosFalso()


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


nucleo.pausa = pausa_corta

URL = levantar_servidor()
TODOS = ["pajaros", "escritura", "cajas", "operaciones"]
FINALES = ("match_over", "practice_summary", "cajas_over", "operacion_over")


def codigo_letra(letra: str) -> list:
    x = (ord(letra) - 65 + 1) / 27
    return [[[x, 0.5], [x, 0.6]]]


def codigo_digito(digito: int) -> list:
    x = (digito + 1) / 10
    return [[[x, 0.2], [x, 0.8]]]


def resultado_de(texto: str) -> str:
    a, operador, b = texto.split(" ")
    a, b = int(a), int(b)
    return str({"+": a + b, "−": a - b, "×": a * b}[operador])


async def jugar_secuencia(juegos: list[str]) -> Cliente:
    ws = await websockets.connect(URL)
    cliente = Cliente(ws)
    await cliente.enviar({"type": "individual", "nombre": "Solo", "juegos": juegos})

    bienvenida = await cliente.esperar("room_created")
    assert bienvenida["modo"] == "individual", bienvenida
    assert bienvenida["practica"] is True, bienvenida
    esperados = [j for j in TODOS if j in juegos]
    assert bienvenida["juegos"] == esperados, bienvenida

    conteo = 0
    palabra = ""
    operacion = ""
    procesados: dict[str, int] = {}
    fin = time.monotonic() + 30

    while time.monotonic() < fin:
        recibidos = cliente.recibidos
        for indice, msg in enumerate(recibidos):
            tipo = msg["type"]
            if indice < procesados.get(tipo, 0):
                continue
            procesados[tipo] = indice + 1
            if tipo == "birds_show":
                conteo = len(msg["aves"])
            elif tipo == "birds_hide":
                await cliente.enviar({"type": "bird_answer", "count": conteo})
                conteo = 0
            elif tipo == "word_show":
                palabra = msg["palabra"]
            elif tipo == "word_write":
                for posicion, letra in enumerate(palabra):
                    await cliente.enviar(
                        {
                            "type": "letter",
                            "index": posicion,
                            "trazos": codigo_letra(letra),
                        }
                    )
            elif tipo == "cajas_hide":
                pilas = [m for m in recibidos[:indice] if m["type"] == "cajas_show"]
                if pilas:
                    total = sum(sum(fila) for fila in pilas[-1]["alturas"])
                    await cliente.enviar({"type": "cajas_answer", "count": total})
            elif tipo == "operacion_show":
                operacion = msg["texto"]
            elif tipo == "operacion_write":
                for posicion, digito in enumerate(resultado_de(operacion)):
                    await cliente.enviar(
                        {
                            "type": "digit",
                            "index": posicion,
                            "trazos": codigo_digito(int(digito)),
                        }
                    )
        if cliente.de_tipo("individual_summary"):
            break
        await asyncio.sleep(0.01)

    assert cliente.de_tipo("individual_summary"), "No llegó el resumen final"
    return cliente


async def secuencia_completa() -> None:
    cliente = await jugar_secuencia(TODOS)
    inicios = cliente.de_tipo("individual_game_start")
    assert [m["juego"] for m in inicios] == TODOS, inicios
    assert [m["indice"] for m in inicios] == [1, 2, 3, 4], inicios
    assert all(m["total"] == 4 for m in inicios), inicios
    for mensaje, nombre in zip(inicios, ("HÁMSTERS", "PALABRAS", "CAJAS", "OPERACIONES")):
        assert mensaje["nombre_juego"] == nombre, mensaje

    # Durante la secuencia no se envía ningún cierre de juego individual.
    for tipo in FINALES:
        assert not cliente.de_tipo(tipo), f"Llegó {tipo} durante la secuencia"

    resumen = cliente.de_tipo("individual_summary")[-1]
    assert resumen["orden"] == TODOS, resumen
    assert set(resumen["resumen"]) == set(TODOS), resumen
    assert resumen["resumen"]["cajas"]["rondas"] == 10
    assert resumen["resumen"]["operaciones"]["rondas"] == 10
    assert resumen["resumen"]["pajaros"]["victorias"] == 3
    assert resumen["resumen"]["escritura"]["victorias"] == 3
    total = sum(dato.get("brain_age", 0) for dato in resumen["resumen"].values())
    assert resumen["total"] == total and total > 0, resumen

    assert len(cliente.de_tipo("cajas_result")) == 10
    assert len(cliente.de_tipo("operacion_result")) == 10
    modos = [m.get("modo", "partida") for m in cliente.de_tipo("match_start")]
    assert modos == ["individual", "individual", "cajas", "operaciones"], modos

    # El resumen permite repetir la misma secuencia sin reconectar.
    await cliente.enviar({"type": "individual_restart"})
    reinicio = await cliente.esperar("individual_game_start", desde=len(inicios))
    assert reinicio["juego"] == "pajaros" and reinicio["indice"] == 1, reinicio
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
    print("Secuencia completa: orden, resumen conjunto y repetición correctos")


async def subconjunto_y_orden() -> None:
    cliente = await jugar_secuencia(["operaciones", "pajaros"])
    inicios = cliente.de_tipo("individual_game_start")
    # El orden es canónico aunque el cliente envíe otra secuencia.
    assert [m["juego"] for m in inicios] == ["pajaros", "operaciones"], inicios

    resumen = cliente.de_tipo("individual_summary")[-1]
    assert set(resumen["resumen"]) == {"pajaros", "operaciones"}, resumen
    for tipo in FINALES:
        assert not cliente.de_tipo(tipo), f"Llegó {tipo} durante la secuencia"
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
    print("Subconjunto: orden canónico y sin cierres intermedios correctos")


async def un_solo_juego_y_validacion() -> None:
    ws = await websockets.connect(URL)
    cliente = Cliente(ws)
    await cliente.enviar({"type": "individual", "nombre": "Solo", "juegos": ["cajas"]})
    bienvenida = await cliente.esperar("room_created")
    assert bienvenida["juegos"] == ["cajas"], bienvenida

    inicio = await cliente.esperar("individual_game_start")
    assert inicio["juego"] == "cajas" and inicio["total"] == 1, inicio
    await cliente.cerrar()

    ws = await websockets.connect(URL)
    cliente = Cliente(ws)
    await cliente.enviar({"type": "individual", "nombre": "Solo", "juegos": ["otro"]})
    error = await cliente.esperar("error")
    assert "válido" in error["mensaje"], error
    await cliente.cerrar()

    while servidor.salas:
        await asyncio.sleep(0.01)
    print("Un juego y validación de juegos incorrectos correctos")


async def main() -> None:
    await secuencia_completa()
    await subconjunto_y_orden()
    await un_solo_juego_y_validacion()


if __name__ == "__main__":
    asyncio.run(main())
