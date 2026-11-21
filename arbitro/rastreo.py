"""Árbitro de RASTREO DE HÁMSTERS: observación, entradas e identificación."""
from __future__ import annotations

import asyncio
import time

from juego.rastreo import CELDAS, RONDAS_RASTREO, GameManager, ScoreManager, nivel_para_ronda
from arbitro import nucleo
from arbitro.puntuacion import brain_age_y_puntos
from arbitro.nucleo import (
    Jugador,
    Sala,
    ajuste_actual,
    clasificacion,
    difundir_roles,
    emitir_progreso_vivo,
    esperar,
    filas_avance_respuestas,
    nombre_de,
    participantes,
    registrar_resultado_individual,
    rondas_para,
)

TIEMPO_IDENTIFICACION = 12.0
PAUSA_ENTRE_RONDAS = 2.5


def resumen_rastreo_individual(sala: Sala) -> dict:
    """Indicadores finales calculados desde lo acumulado en la sala."""
    datos = sala.datos.get("rastreo", {})
    rondas = datos.get("rondas", 0)
    aciertos = datos.get("aciertos", 0)
    errores = datos.get("errores", 0)
    tiempo = datos.get("tiempo", 0.0)
    brain, puntos = brain_age_y_puntos(tiempo, errores)
    return {
        "rondas": rondas,
        "aciertos": aciertos,
        "errores": errores,
        "brain_age": round(brain, 2),
        "precision": round(100 * aciertos / (2 * rondas), 1) if rondas else 0.0,
        "tiempo_promedio": round(tiempo / rondas, 2) if rondas else 0.0,
        "tiempo_total": round(tiempo, 2),
        "puntos": puntos,
    }


async def manejar_respuesta_rastreo(
    sala: Sala, jugador: Jugador, mensaje: dict
) -> None:
    """Valida la identificación: fase, ronda, mando, dos casillas y una sola vez."""
    if sala.fase != "rastreo" or sala.datos.get("momento_respuesta") is None:
        return
    if sala.modo == "fiesta" and jugador.rol != "mando":
        return
    if mensaje.get("ronda") != sala.datos.get("ronda"):
        return
    if jugador.id in sala.respuestas:
        return

    respuesta = mensaje.get("respuesta")
    if not isinstance(respuesta, (list, tuple)) or len(respuesta) != 2:
        return
    if any(
        isinstance(celda, bool)
        or not isinstance(celda, int)
        or not 0 <= celda < CELDAS
        for celda in respuesta
    ):
        return
    if respuesta[0] == respuesta[1]:
        return

    seleccion = (respuesta[0], respuesta[1])
    evaluacion = ScoreManager.evaluar(seleccion, sala.datos["plan"]["final"])
    sala.respuestas[jugador.id] = (seleccion, time.monotonic())
    await jugador.enviar(
        {
            "type": "rastreo_feedback",
            "pid": jugador.id,
            "acepta": evaluacion["aciertos"] == 2,
            "aciertos": evaluacion["aciertos"],
            "precision": evaluacion["precision"],
        }
    )
    if sala.modo == "fiesta":
        # La pantalla ve quién terminó, nunca qué casillas eligió.
        await emitir_progreso_vivo(
            sala,
            "rastreo",
            filas_avance_respuestas(sala, sala.respuestas),
            sala.datos.get("ronda"),
        )
    if len(sala.respuestas) >= len(participantes(sala)):
        sala.evento_respuestas.set()


async def bucle_rastreo(sala: Sala) -> None:
    """Cuenta previa, observación, entradas e identificación en cada ronda."""
    jugadores_ = participantes(sala)
    ids = [j.id for j in jugadores_]
    principal = ids[0] if ids else sala.host_id
    tiempos = {pid: 0.0 for pid in ids}
    fallos = {pid: 0 for pid in ids}
    aciertos = {pid: 0 for pid in ids}
    puntos = {pid: 0 for pid in ids}
    sala.ultimos_puntos = {}
    rondas = rondas_para(sala, RONDAS_RASTREO)
    dificultad_base = ajuste_actual(sala).get("dificultad", "facil")
    sala.datos = {
        "juego": "rastreo",
        "ronda": 0,
        "momento_respuesta": None,
        "rastreo": {"rondas": 0, "aciertos": 0, "errores": 0, "tiempo": 0.0},
    }

    try:
        await nucleo.pausa(sala, 0.6)
        if sala.cancelada:
            return
        sala.fase = "rastreo"
        await sala.difundir(
            {
                "type": "match_start",
                "modo": "rastreo",
                "necesario": rondas,
            }
        )

        for ronda in range(1, rondas + 1):
            if sala.cancelada:
                return
            dificultad = nivel_para_ronda(dificultad_base, ronda)
            plan = GameManager.generar(dificultad)
            parametros = plan["parametros"]
            sala.datos.update(
                {
                    "ronda": ronda,
                    "plan": plan,
                    "dificultad": dificultad,
                    "momento_respuesta": None,
                }
            )
            sala.respuestas = {}
            sala.evento_respuestas.clear()

            if sala.modo == "fiesta":
                await emitir_progreso_vivo(
                    sala, "rastreo", filas_avance_respuestas(sala, ()), ronda
                )

            await sala.difundir(
                {
                    "type": "rastreo_countdown",
                    "segundos": nucleo.TIEMPO_CUENTA_PREVIA,
                    "ronda": ronda,
                    "necesario": rondas,
                    "dificultad": dificultad,
                }
            )
            await nucleo.pausa(sala, nucleo.TIEMPO_CUENTA_PREVIA)
            if sala.cancelada:
                return

            await difundir_roles(
                sala,
                {
                    "type": "rastreo_show",
                    "ronda": ronda,
                    "tablero": plan["observacion"],
                    "duracion": parametros["observacion"],
                    "dificultad": dificultad,
                },
                {
                    "type": "rastreo_show",
                    "ronda": ronda,
                    "mira": True,
                    "duracion": parametros["observacion"],
                    "dificultad": dificultad,
                },
            )
            await nucleo.pausa(sala, parametros["observacion"])
            if sala.cancelada:
                return

            await sala.difundir({"type": "rastreo_hide", "ronda": ronda})
            total = len(plan["movimientos"])
            for indice, movimiento in enumerate(plan["movimientos"], start=1):
                if sala.cancelada:
                    return
                await difundir_roles(
                    sala,
                    {
                        "type": "rastreo_move",
                        "ronda": ronda,
                        "indice": indice,
                        "total": total,
                        "lado": movimiento["lado"],
                        "linea": movimiento["linea"],
                        "duracion": movimiento["duracion"],
                        "salida": movimiento["salida"],
                        "reaparecio": movimiento["reaparecio"],
                    },
                    {
                        "type": "rastreo_move",
                        "ronda": ronda,
                        "indice": indice,
                        "total": total,
                        "lado": movimiento["lado"],
                        "linea": movimiento["linea"],
                        "duracion": movimiento["duracion"],
                    },
                )
                await nucleo.pausa(sala, parametros["intervalo"])
                if sala.cancelada:
                    return

            sala.datos["momento_respuesta"] = time.monotonic()
            await difundir_roles(
                sala,
                {
                    "type": "rastreo_write",
                    "ronda": ronda,
                    "celdas": CELDAS,
                    "necesario": rondas,
                    "dificultad": dificultad,
                },
                {
                    "type": "rastreo_write",
                    "ronda": ronda,
                    "celdas": CELDAS,
                    "mira": True,
                },
            )
            await esperar(sala, sala.evento_respuestas, TIEMPO_IDENTIFICACION)
            if sala.cancelada:
                return

            ahora = time.monotonic()
            por_jugador: dict[str, dict] = {}
            for jugador in jugadores_:
                pid = jugador.id
                respuesta = sala.respuestas.get(pid)
                seleccion = respuesta[0] if respuesta else ()
                evaluacion = ScoreManager.evaluar(seleccion, plan["final"])
                acierto_ronda = evaluacion["aciertos"]
                fin = respuesta[1] if respuesta else ahora
                tiempo = (
                    max(0.0, fin - sala.datos["momento_respuesta"])
                    if respuesta
                    else TIEMPO_IDENTIFICACION
                )
                aciertos[pid] += acierto_ronda
                fallos[pid] += evaluacion["errores"]
                tiempos[pid] += tiempo
                brain, puntos[pid] = brain_age_y_puntos(tiempos[pid], fallos[pid])
                por_jugador[pid] = {
                    "seleccion": list(seleccion),
                    "aciertos": acierto_ronda,
                    "errores": evaluacion["errores"],
                    "precision": evaluacion["precision"],
                    "tiempo": round(tiempo, 2),
                    "brain_age": round(brain, 2),
                    "puntos": puntos[pid],
                }

            datos_principal = por_jugador.get(principal, {})
            sala.datos["rastreo"] = {
                "rondas": ronda,
                "aciertos": aciertos.get(principal, 0),
                "errores": fallos.get(principal, 0),
                "tiempo": tiempos.get(principal, 0.0),
            }
            await difundir_roles(
                sala,
                {
                    "type": "rastreo_result",
                    "ronda": ronda,
                    "necesario": rondas,
                    "dificultad": dificultad,
                    "reto": {
                        "final": list(plan["final"].values()),
                        "aciertos": {
                            pid: dato["aciertos"] for pid, dato in por_jugador.items()
                        },
                    },
                    "jugadores": por_jugador,
                    "clasificacion": clasificacion(sala),
                    **datos_principal,
                },
                {"type": "rastreo_result", "ronda": ronda},
            )
            await nucleo.pausa(
                sala, PAUSA_ENTRE_RONDAS if ronda < rondas else 1.0
            )

        resumen = resumen_rastreo_individual(sala)
        if sala.secuencia_individual:
            registrar_resultado_individual(sala, "rastreo", resumen)
            return

        sala.fase = "fin"
        sala.ultimos_puntos = dict(puntos)
        await difundir_roles(
            sala,
            {
                "type": "rastreo_over",
                "nombre": nombre_de(sala, principal),
                "clasificacion": [
                    {
                        "id": pid,
                        "nombre": nombre_de(sala, pid),
                        "puntos": puntos[pid],
                        "brain_age": round(
                            brain_age_y_puntos(tiempos[pid], fallos[pid])[0], 2
                        ),
                    }
                    for pid in ids
                ],
                **resumen,
            },
            {"type": "rastreo_over"},
        )
    except asyncio.CancelledError:
        raise
