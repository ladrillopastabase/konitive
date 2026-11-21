"""OPERACIONES: cuentas rápidas respondidas con cifras manuscritas."""
from __future__ import annotations

import asyncio
import time

from juego.operaciones import generar_operacion
from arbitro import nucleo
from arbitro.puntuacion import brain_age_y_puntos, fallos_escritura
from arbitro.nucleo import (
    Sala,
    TIEMPO_CUENTA_PREVIA,
    clasificacion,
    difundir_roles,
    emitir_progreso_vivo,
    esperar,
    filas_avance_escritura,
    nombre_de,
    participantes,
    registrar_resultado_individual,
    ronda_generador,
    rondas_para,
)


# Operaciones: misma mecánica que palabras, pero con cifras manuscritas.
RONDAS_OPERACIONES = 10
TIEMPO_FLASH_OPERACION = 0.9
TIEMPO_ESPERA_OPERACIONES = 60


def marcador_operaciones(
    sala: Sala, puntos: dict[str, int], ronda: int
) -> dict:
    ids = [j.id for j in participantes(sala)]
    primero = ids[0] if ids else sala.host_id
    return {
        "operaciones": {
            pid: {"puntos": puntos.get(pid, 0), "ronda": ronda} for pid in ids
        },
        "nombre": sala.jugadores[primero].nombre
        if primero in sala.jugadores
        else "JUGADOR",
        "necesario": rondas_para(sala, RONDAS_OPERACIONES),
    }


async def bucle_operaciones(sala: Sala) -> None:
    """Diez operaciones; en fiesta todos los mandos escriben a la vez."""
    jugadores_ = participantes(sala)
    ids = [j.id for j in jugadores_]
    puntos = {pid: 0 for pid in ids}
    tiempos = {pid: 0.0 for pid in ids}
    errores = {pid: 0 for pid in ids}
    anterior: str | None = None
    sala.ultimos_puntos = {}
    rondas = rondas_para(sala, RONDAS_OPERACIONES)

    try:
        await nucleo.pausa(sala, 0.6)
        if sala.cancelada:
            return
        sala.fase = "operaciones"
        await sala.difundir(
            {
                "type": "match_start",
                "modo": "operaciones",
                "marcador": marcador_operaciones(sala, puntos, 0),
            }
        )

        for ronda in range(1, rondas + 1):
            if sala.cancelada:
                return
            operacion = generar_operacion(
                ronda_generador(sala, ronda, (0, 3, 6)), anterior
            )
            anterior = operacion["texto"]
            sala.datos = {
                "juego": "operaciones",
                "nivel": operacion["nivel"],
                "ronda": ronda,
                "operacion": operacion,
                "momento_respuesta": None,
                "escribiendo": False,
            }
            sala.evento_escritura.clear()
            for jugador in jugadores_:
                jugador.progreso = {
                    "resultado": operacion["resultado"],
                    "digitos": [
                        {"intentos": 0, "puntos": 0, "estado": "pendiente", "motivo": ""}
                        for _ in operacion["resultado"]
                    ],
                    "inicio": None,
                    "fin": None,
                }

            if sala.modo == "fiesta":
                await emitir_progreso_vivo(
                    sala,
                    "operaciones",
                    filas_avance_escritura(sala, "operaciones", "digitos", "resultado"),
                    ronda,
                )

            await sala.difundir(
                {
                    "type": "operacion_countdown",
                    "segundos": TIEMPO_CUENTA_PREVIA,
                    "ronda": ronda,
                    "necesario": rondas,
                    "dificultad": operacion["dificultad"],
                    "marcador": marcador_operaciones(sala, puntos, ronda),
                }
            )
            await nucleo.pausa(sala, TIEMPO_CUENTA_PREVIA)
            if sala.cancelada:
                return

            await difundir_roles(
                sala,
                {
                    "type": "operacion_show",
                    "texto": operacion["texto"],
                    "flash": TIEMPO_FLASH_OPERACION,
                    "ronda": ronda,
                    "dificultad": operacion["dificultad"],
                },
                # Los mandos no reciben el enunciado: deben mirar la pantalla.
                {
                    "type": "operacion_show",
                    "flash": TIEMPO_FLASH_OPERACION,
                    "ronda": ronda,
                    "dificultad": operacion["dificultad"],
                },
            )
            await nucleo.pausa(sala, TIEMPO_FLASH_OPERACION)
            if sala.cancelada:
                return

            inicio = time.monotonic()
            for jugador in jugadores_:
                jugador.progreso["inicio"] = inicio
            sala.datos["escribiendo"] = True
            await sala.difundir(
                {
                    "type": "operacion_write",
                    "ronda": ronda,
                    "marcador": marcador_operaciones(sala, puntos, ronda),
                }
            )
            await esperar(sala, sala.evento_escritura, TIEMPO_ESPERA_OPERACIONES)
            if sala.cancelada:
                return

            desglose: dict[str, dict] = {}
            for jugador in jugadores_:
                progreso = jugador.progreso
                fin = progreso.get("fin")
                tiempo = (
                    max(0.0, fin - inicio)
                    if fin is not None
                    else float(TIEMPO_ESPERA_OPERACIONES)
                )
                fallos = fallos_escritura(progreso["digitos"], incompleto=fin is None)
                automaticas = sum(
                    1 for d in progreso["digitos"] if d["motivo"] == "automatica"
                )
                correctas = sum(
                    1 for d in progreso["digitos"] if d["motivo"] != "automatica"
                )

                pid = jugador.id
                tiempos[pid] += tiempo
                errores[pid] += fallos
                brain, puntos[pid] = brain_age_y_puntos(
                    tiempos[pid], errores[pid]
                )
                desglose[pid] = {
                    "tiempo": tiempo,
                    "errores": fallos,
                    "brain_age": brain,
                    "total": puntos[pid],
                    "correctas": correctas,
                    "automaticas": automaticas,
                }

            # En FIESTA el enunciado y el resultado se revelan solo en la
            # pantalla: el mando no recibe la operación resuelta.
            await difundir_roles(
                sala,
                {
                    "type": "operacion_result",
                    "texto": operacion["texto"],
                    "resultado": operacion["resultado"],
                    "ronda": ronda,
                    "necesario": rondas,
                    "dificultad": operacion["dificultad"],
                    "desglose": desglose,
                    "clasificacion": clasificacion(sala),
                    "marcador": marcador_operaciones(sala, puntos, ronda),
                },
                {"type": "operacion_result", "ronda": ronda},
            )
            await nucleo.pausa(sala, 3.0 if ronda < rondas else 1.0)

        primero = ids[0] if ids else sala.host_id
        tiempo_total = tiempos.get(primero, 0.0)
        fallos_totales = errores.get(primero, 0)
        brain_final, puntos_final = brain_age_y_puntos(tiempo_total, fallos_totales)
        if sala.secuencia_individual:
            registrar_resultado_individual(
                sala,
                "operaciones",
                {
                    "rondas": rondas,
                    "puntos": puntos.get(primero, 0),
                    "tiempo_total": tiempo_total,
                    "errores": fallos_totales,
                    "brain_age": brain_final,
                },
            )
            return

        sala.fase = "fin"
        sala.ultimos_puntos = dict(puntos)
        await sala.difundir(
            {
                "type": "operacion_over",
                "puntos": puntos_final,
                "tiempo_total": tiempo_total,
                "errores": fallos_totales,
                "brain_age": brain_final,
                "rondas": rondas,
                "nombre": sala.jugadores[primero].nombre
                if primero in sala.jugadores
                else "JUGADOR",
                "clasificacion": [
                    {"id": pid, "nombre": nombre_de(sala, pid), "puntos": puntos[pid]}
                    for pid in ids
                ],
            }
        )
    except asyncio.CancelledError:
        raise
