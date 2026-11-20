"""CAJAS: contar cubos de una pila isométrica en 10 rondas."""
from __future__ import annotations

import asyncio
import time

from juego.cajas import DIFICULTADES, generar_pila
from arbitro import nucleo
from arbitro.nucleo import (
    Sala,
    clasificacion,
    difundir_roles,
    emitir_progreso_vivo,
    esperar,
    filas_avance_respuestas,
    nombre_de,
    participantes,
    registrar_resultado_individual,
    ronda_generador,
    rondas_para,
)


# Cuenta Cajas: modo propio, fuera de JUEGOS para no alterar el mejor-de-3.
RONDAS_CAJAS = 10
TIEMPO_CUENTA_CAJAS = 3.0
TIEMPO_RESPUESTA_CAJAS = 10
PUNTOS_BASE_CAJAS = 100
BONO_MAXIMO_CAJAS = 50
BONO_POR_SEGUNDO_CAJAS = 5


def marcador_cajas(
    sala: Sala,
    puntos: dict[str, int],
    aciertos: dict[str, int],
    rachas: dict[str, int],
    ronda: int,
) -> dict:
    """Marcador de CAJAS; el cliente tiene una rama propia para él."""
    ids = [j.id for j in participantes(sala)]
    primero = ids[0] if ids else sala.host_id
    return {
        "cajas": {
            pid: {
                "puntos": puntos.get(pid, 0),
                "aciertos": aciertos.get(pid, 0),
                "racha": rachas.get(pid, 0),
                "ronda": ronda,
            }
            for pid in ids
        },
        "nombre": sala.jugadores.get(primero, sala.host_id).nombre
        if primero in sala.jugadores
        else "JUGADOR",
        "necesario": rondas_para(sala, RONDAS_CAJAS),
    }


async def bucle_cajas(sala: Sala) -> None:
    """Diez rondas de CAJAS; en fiesta juegan todos los mandos a la vez."""
    jugadores_ = participantes(sala)
    ids = [j.id for j in jugadores_]
    puntos = {pid: 0 for pid in ids}
    aciertos = {pid: 0 for pid in ids}
    rachas = {pid: 0 for pid in ids}
    mejor_racha = {pid: 0 for pid in ids}
    anterior: list[list[int]] | None = None
    sala.ultimos_puntos = {}
    rondas = rondas_para(sala, RONDAS_CAJAS)
    # En fiesta la dificultad fija el punto de partida (FÁCIL/NORMAL/DIFÍCIL).
    dificultad_base = ronda_generador(sala, 0, (0, 1, 2))

    try:
        await nucleo.pausa(sala, 0.6)
        if sala.cancelada:
            return
        sala.fase = "cajas"
        await sala.difundir(
            {
                "type": "match_start",
                "modo": "cajas",
                "marcador": marcador_cajas(sala, puntos, aciertos, rachas, 0),
            }
        )

        for ronda in range(1, rondas + 1):
            if sala.cancelada:
                return
            racha_referencia = max(rachas.values(), default=0)
            indice_dificultad = min(
                len(DIFICULTADES) - 1, dificultad_base + racha_referencia // 3
            )
            pila = generar_pila(indice_dificultad, anterior)
            anterior = pila["alturas"]
            multiplicador = 1 + indice_dificultad

            sala.datos = {
                "juego": "cajas",
                "nivel": indice_dificultad + 1,
                "ronda": ronda,
                "pila": pila,
                "momento_respuesta": None,
            }
            sala.respuestas = {}
            sala.evento_respuestas.clear()

            if sala.modo == "fiesta":
                await emitir_progreso_vivo(
                    sala, "cajas", filas_avance_respuestas(sala, ()), ronda
                )

            await sala.difundir(
                {
                    "type": "cajas_countdown",
                    "segundos": TIEMPO_CUENTA_CAJAS,
                    "ronda": ronda,
                    "necesario": rondas,
                    "dificultad": pila["dificultad"],
                    "marcador": marcador_cajas(
                        sala, puntos, aciertos, rachas, ronda
                    ),
                }
            )
            await nucleo.pausa(sala, TIEMPO_CUENTA_CAJAS)
            if sala.cancelada:
                return

            await difundir_roles(
                sala,
                {
                    "type": "cajas_show",
                    "alturas": pila["alturas"],
                    "base": pila["base"],
                    "duracion": pila["segundos"],
                    "ronda": ronda,
                    "dificultad": pila["dificultad"],
                    "total": pila["total"],
                    "visibles": pila["visibles"],
                    "ocultas": pila["ocultas"],
                },
                # En fiesta la pila solo se ve en la pantalla.
                {
                    "type": "cajas_show",
                    "duracion": pila["segundos"],
                    "ronda": ronda,
                    "dificultad": pila["dificultad"],
                },
            )
            await nucleo.pausa(sala, pila["segundos"])
            if sala.cancelada:
                return

            sala.datos["momento_respuesta"] = time.monotonic()
            await sala.difundir({"type": "cajas_hide"})
            await esperar(sala, sala.evento_respuestas, TIEMPO_RESPUESTA_CAJAS)
            if sala.cancelada:
                return

            por_jugador: dict[str, dict] = {}
            for jugador in jugadores_:
                pid = jugador.id
                respuesta = sala.respuestas.get(pid)
                elegida = respuesta[0] if respuesta else None
                acierto = elegida == pila["total"]
                bono = 0
                if acierto and respuesta:
                    tardanza = max(
                        0.0, respuesta[1] - sala.datos["momento_respuesta"]
                    )
                    bono = max(
                        0, BONO_MAXIMO_CAJAS - int(tardanza * BONO_POR_SEGUNDO_CAJAS)
                    )
                if acierto:
                    aciertos[pid] += 1
                    rachas[pid] += 1
                    mejor_racha[pid] = max(mejor_racha[pid], rachas[pid])
                else:
                    rachas[pid] = 0
                puntos_ronda = (
                    (PUNTOS_BASE_CAJAS + bono) * multiplicador if acierto else 0
                )
                puntos[pid] += puntos_ronda
                por_jugador[pid] = {
                    "elegida": elegida,
                    "acierto": acierto,
                    "puntos": puntos_ronda,
                    "bono": bono,
                    "racha": rachas[pid],
                }

            # Campos planos del primer jugador: compatibles con el modo individual.
            principal = por_jugador[ids[0]] if ids else {}
            # En FIESTA el informe se ve solo en la pantalla; el mando no recibe
            # la pila revelada ni cuántas cajas había.
            await difundir_roles(
                sala,
                {
                    "type": "cajas_result",
                    "alturas": pila["alturas"],
                    "base": pila["base"],
                    "total": pila["total"],
                    "visibles": pila["visibles"],
                    "multiplicador": multiplicador,
                    "ronda": ronda,
                    "necesario": rondas,
                    "dificultad": pila["dificultad"],
                    "jugadores": por_jugador,
                    "clasificacion": clasificacion(sala),
                    "marcador": marcador_cajas(
                        sala, puntos, aciertos, rachas, ronda
                    ),
                    **principal,
                },
                {"type": "cajas_result", "ronda": ronda},
            )
            await nucleo.pausa(sala, 3.0 if ronda < rondas else 1.0)

        if sala.secuencia_individual:
            registrar_resultado_individual(
                sala,
                "cajas",
                {
                    "rondas": rondas,
                    "puntos": sum(puntos.values()),
                    "aciertos": aciertos.get(ids[0], 0) if ids else 0,
                    "mejor_racha": max(mejor_racha.values(), default=0),
                },
            )
            return

        sala.fase = "fin"
        sala.ultimos_puntos = dict(puntos)
        primero = ids[0] if ids else sala.host_id
        await sala.difundir(
            {
                "type": "cajas_over",
                "puntos": sum(puntos.values()),
                "aciertos": aciertos.get(primero, 0),
                "mejor_racha": max(mejor_racha.values(), default=0),
                "rondas": rondas,
                "nombre": sala.jugadores[primero].nombre
                if primero in sala.jugadores
                else "JUGADOR",
                "clasificacion": [
                    {
                        "id": pid,
                        "nombre": nombre_de(sala, pid),
                        "puntos": puntos[pid],
                        "aciertos": aciertos[pid],
                    }
                    for pid in ids
                ],
            }
        )
    except asyncio.CancelledError:
        raise
