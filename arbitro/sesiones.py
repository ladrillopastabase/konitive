"""Orquestadores que encadenan juegos: secuencia INDIVIDUAL y FIESTA."""
from __future__ import annotations

import asyncio

from juego.minijuegos import JUEGOS_MINI
from arbitro import nucleo
from arbitro.nucleo import JUEGOS, NOMBRES_JUEGOS, Sala, clasificacion, emitir_podium
from arbitro.clasico import bucle_partida
from arbitro.cajas import bucle_cajas
from arbitro.operaciones import bucle_operaciones
from arbitro.minijuegos import bucle_minijuego
from arbitro.rastreo import bucle_rastreo


# Bucle de cada juego del catálogo. Un juego nuevo se registra aquí.
BUCLES = {
    **{juego: bucle_partida for juego in JUEGOS},
    "cajas": bucle_cajas,
    "operaciones": bucle_operaciones,
    "rastreo": bucle_rastreo,
    **{juego: (lambda sala, juego=juego: bucle_minijuego(sala, juego)) for juego in JUEGOS_MINI},
}


async def jugar(sala: Sala, juego: str) -> None:
    """Lanza el bucle del juego indicado y espera a que termine."""
    await BUCLES[juego](sala)


async def bucle_individual(sala: Sala) -> None:
    """Juega uno detrás de otro los juegos elegidos y entrega un resumen común."""
    pid = next(iter(sala.jugadores), sala.host_id)
    nombre = sala.jugadores[pid].nombre if pid in sala.jugadores else "JUGADOR"
    try:
        total = len(sala.juegos_individual)
        for indice, juego in enumerate(sala.juegos_individual, start=1):
            if sala.cancelada:
                return
            sala.juego_individual = juego
            sala.fase = "entre_juegos"
            await sala.difundir(
                {
                    "type": "individual_game_start",
                    "juego": juego,
                    "nombre_juego": NOMBRES_JUEGOS.get(juego, juego.upper()),
                    "indice": indice,
                    "total": total,
                }
            )
            await nucleo.pausa(sala, 1.2)
            if sala.cancelada:
                return

            sala.reiniciar_marcador()
            sala.fase = "jugando"
            await jugar(sala, juego)
            if sala.cancelada:
                return

        sala.fase = "fin"
        await sala.difundir(
            {
                "type": "individual_summary",
                "nombre": nombre,
                "resumen": sala.resultados_individual,
                "orden": sala.juegos_individual,
                "total": sum(
                    dato.get("puntuacion", 0.0)
                    for dato in sala.resultados_individual.values()
                ),
            }
        )
    except asyncio.CancelledError:
        pass


async def bucle_fiesta(sala: Sala) -> None:
    """Juega la lista elegida en el lobby, con el podio entre un juego y otro."""
    juegos = sala.juegos_fiesta
    for i, juego in enumerate(juegos):
        if sala.cancelada:
            return
        sala.juego_fiesta = juego
        sala.podium_antes = clasificacion(sala)
        sala.reiniciar_marcador()
        sala.fase = "jugando"
        await jugar(sala, juego)
        if sala.cancelada:
            return
        siguiente = juegos[i + 1] if i + 1 < len(juegos) else None
        await emitir_podium(sala, siguiente=siguiente)
