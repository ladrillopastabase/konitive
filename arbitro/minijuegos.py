"""Los ocho minijuegos de entrenamiento y la validación de sus respuestas."""
from __future__ import annotations

import asyncio
import time

from juego.minijuegos import (
    DENOMINACIONES_CLP, JUEGOS_ESCRITURA, MANOS, RONDAS_MINI, generar,
)
from arbitro import nucleo
from arbitro.puntuacion import brain_age
from arbitro.nucleo import (
    Jugador,
    Sala,
    clasificacion,
    difundir_roles,
    emitir_progreso_vivo,
    esperar,
    participantes,
    reconocer_en_hilo,
    ronda_generador,
    rondas_para,
    trazos_validos,
)


# Minijuegos de entrenamiento: el puntaje Brain Age es tiempo + 5 s por error
# (menor es mejor). Es el único resultado, también en el podio.
TIEMPO_CUENTA_MINI = 3.0
TIEMPO_RESPUESTA_MINI = {
    "stroop": 3.0,
    "triangulos": 60.0,
    "relojes": 60.0,
    "menor": 30.0,
    "memoria": 20.0,
    "vuelto": 30.0,
    "silabas": 60.0,
    "ppt": 4.0,
}
# Stroop: la palabra se ve menos tiempo cuanto más avanza la dificultad. El
# plazo para responder no cambia (TIEMPO_RESPUESTA_MINI["stroop"]).
EXPOSICION_STROOP_INICIAL = 1.2
EXPOSICION_STROOP_FINAL = 0.5


def exposicion_stroop(ronda: int) -> float:
    """Segundos que se ve la palabra: 1,2 s en la ronda 1 y 0,5 s en la 20."""
    progreso = (ronda - 1) / max(1, RONDAS_MINI["stroop"] - 1)
    return round(
        max(
            EXPOSICION_STROOP_FINAL,
            EXPOSICION_STROOP_INICIAL
            - (EXPOSICION_STROOP_INICIAL - EXPOSICION_STROOP_FINAL) * progreso,
        ),
        2,
    )
# Campos que el árbitro guarda pero que jamás deben viajar en el estímulo.
SECRETOS_MINI = {
    "stroop": ("correcta", "clave"),
    "triangulos": ("intermedios", "resultado", "esperado"),
    "relojes": ("horas", "minutos", "esperado", "digital1", "digital2"),
    "menor": ("orden",),
    "memoria": (),  # la pantalla necesita la grilla; solo los mandos la ocultan
    "vuelto": ("vuelto", "vuelto_texto", "optimo"),
    "silabas": ("silabas", "total", "esperado", "pista"),
    "ppt": ("esperado",),
}

# Estos siguen el patrón de HÁMSTERS y CAJAS: el dibujo grande queda en
# la PC y el celular solo recibe los controles para responder.
MINIJUEGOS_SOLO_PANTALLA = frozenset(
    {"stroop", "triangulos", "relojes", "vuelto", "silabas", "ppt"}
)
VISUAL_MINI = {
    "stroop": ("palabra", "tinta"),
    "triangulos": ("top", "ops", "op_final"),
    "relojes": ("reloj1", "reloj2", "periodo1", "periodo2"),
    "vuelto": ("producto", "precio_texto", "pago_texto"),
    "silabas": ("frase",),
    "ppt": ("rival", "objetivo"),
}


# ---------------------------------------------------------------------------
# Minijuegos de entrenamiento (Stroop, Triángulos, Relojes, Menor a mayor,
# Memoria, Vuelto, Sílabas y Piedra papel tijera). Todos comparten este bucle: la fase lleva el
# nombre del juego, las respuestas incluyen ronda y jugador, y el host mide
# los tiempos y calcula el puntaje Brain Age.
# ---------------------------------------------------------------------------
def marcador_mini(
    sala: Sala, juego: str, tiempos_brain: dict[str, float], ronda: int
) -> dict:
    ids = [j.id for j in participantes(sala)]
    primero = ids[0] if ids else sala.host_id
    return {
        juego: {
            pid: {"brain_age": tiempos_brain.get(pid, 0.0), "ronda": ronda} for pid in ids
        },
        "nombre": sala.jugadores[primero].nombre
        if primero in sala.jugadores
        else "JUGADOR",
        "necesario": rondas_para(sala, RONDAS_MINI[juego]),
    }


def datos_para_resultado(juego: str, reto: dict) -> dict:
    """Solo los campos que deben revelarse al terminar la ronda."""
    claves = {
        "stroop": ("palabra", "tinta", "correcta"),
        "triangulos": ("top", "ops", "op_final", "intermedios", "resultado"),
        "relojes": (
            "reloj1", "reloj2", "periodo1", "periodo2",
            "digital1", "digital2", "horas", "minutos",
        ),
        "menor": ("numeros", "orden"),
        "memoria": ("grilla", "posiciones", "cantidad"),
        "vuelto": ("producto", "precio_texto", "pago_texto", "vuelto_texto", "optimo"),
        "silabas": ("frase", "silabas", "pista", "total"),
        "ppt": ("rival", "objetivo", "esperado"),
    }[juego]
    return {clave: reto[clave] for clave in claves}


def visual_mini(juego: str, reto: dict) -> dict:
    """Campos visuales que la pantalla necesita para dibujar el estímulo."""
    return {clave: reto[clave] for clave in VISUAL_MINI.get(juego, ())}


def estimulo_para_mando(juego: str, reto: dict) -> dict:
    """Lo que el celular puede mostrar sin revelar la respuesta correcta.

    En los juegos de patrón amplio y en Memoria el mando solo mira la PC.
    Menor a mayor necesita las posiciones para tocarlas y no revela el orden.
    """
    if juego in MINIJUEGOS_SOLO_PANTALLA or juego == "memoria":
        return {"mira": True}
    if juego == "menor":
        return {"numeros": reto["numeros"]}
    return {}


def filas_avance_mini(sala: Sala, juego: str) -> list[dict]:
    """Avance por ronda de cada mando; nunca incluye la respuesta correcta."""
    filas = []
    for jugador in participantes(sala):
        progreso = jugador.progreso or {}
        if juego in JUEGOS_ESCRITURA:
            digitos = progreso.get("digitos", [])
            avance = sum(1 for c in digitos if c.get("estado") == "aceptada")
            total = len(progreso.get("esperado", "")) or len(digitos)
            activo = avance or any(c.get("intentos") for c in digitos)
        else:
            secuencia = progreso.get("secuencia", [])
            avance = len(secuencia)
            total = progreso.get("total", 0)
            if not total:
                reto = sala.datos.get("reto", {})
                total = (
                    reto.get("cantidad", 1)
                    if juego in ("menor", "memoria")
                    else 1
                )
            activo = bool(secuencia)
        filas.append(
            {
                "id": jugador.id,
                "nombre": jugador.nombre,
                "avance": avance,
                "total": total,
                "estado": (
                    "listo"
                    if progreso.get("fin") is not None
                    else "contando"
                    if activo
                    else "esperando"
                ),
            }
        )
    return filas


async def _feedback_privado(
    sala: Sala, jugador: Jugador, juego: str, acepta: bool, **extra
) -> None:
    """Feedback verde/rosa solo al jugador que respondió."""
    await jugador.enviar(
        {
            "type": f"{juego}_feedback",
            "pid": jugador.id,
            "acepta": acepta,
            "aceptada": acepta,
            **extra,
        }
    )
    progreso = jugador.progreso
    avance = len(progreso.get("secuencia", []))
    if juego in JUEGOS_ESCRITURA:
        avance = sum(1 for c in progreso.get("digitos", []) if c.get("estado") == "aceptada")
    datos_progreso = {
        "type": "mini_progreso",
        "juego": juego,
        "pid": jugador.id,
        "marcados": avance,
        "total": len(progreso.get("esperado", "")) or progreso.get("total", 0),
        "fallos": progreso.get("fallos", 0),
    }
    if sala.modo == "fiesta":
        # El celular ve solo su avance, nunca el de los demás ni si acertó.
        await jugador.enviar(datos_progreso)
        await emitir_progreso_vivo(
            sala, juego, filas_avance_mini(sala, juego), sala.datos.get("ronda")
        )
    else:
        await sala.difundir(datos_progreso)


async def manejar_respuesta_mini(
    sala: Sala, jugador: Jugador, mensaje: dict, juego: str
) -> None:
    """Valida la respuesta del celular: ronda vigente, jugador y una sola vez."""
    if sala.fase != juego or sala.datos.get("momento_respuesta") is None:
        return
    if sala.modo == "fiesta" and jugador.rol != "mando":
        return
    if mensaje.get("ronda") != sala.datos.get("ronda"):
        return

    reto = sala.datos["reto"]
    progreso = jugador.progreso
    ahora = time.monotonic()
    if progreso.get("inicio") is None:
        progreso["inicio"] = ahora

    if juego in JUEGOS_ESCRITURA:
        indice = mensaje.get("index")
        esperado = progreso.get("esperado", "")
        if not isinstance(indice, int) or not 0 <= indice < len(esperado):
            return
        casilla = progreso["digitos"][indice]
        if casilla["estado"] == "aceptada" or casilla.get("procesando"):
            return
        trazos = trazos_validos(mensaje)
        if not trazos:
            return
        try:
            predicha, _confianza = await reconocer_en_hilo(
                lambda t: nucleo.reconocedor_digitos.reconocer(t), trazos, casilla
            )
        except Exception:
            return
        if (
            jugador.progreso is not progreso
            or sala.fase != juego
            or mensaje.get("ronda") != sala.datos.get("ronda")
        ):
            return
        acepta = predicha == esperado[indice]
        casilla["intentos"] += 1
        if acepta:
            casilla["estado"] = "aceptada"
            casilla["motivo"] = "aceptada"
        else:
            progreso["fallos"] += 1
        await _feedback_privado(
            sala, jugador, juego, acepta, index=indice, predicha=predicha,
            esperada=esperado[indice] if acepta else None,
            intentos=casilla["intentos"],
        )
        if all(casilla["estado"] == "aceptada" for casilla in progreso["digitos"]):
            progreso["fin"] = ahora
            await jugador.enviar({"type": f"{juego}_done", "pid": jugador.id})
            if all(
                j.progreso.get("fin") is not None for j in participantes(sala)
            ):
                sala.evento_escritura.set()
        return

    respuesta = mensaje.get("respuesta")

    if juego in ("menor", "memoria"):
        # En memoria se tocan casillas (hasta celdas-1); en menor, posiciones
        # de la lista de números (hasta cantidad-1).
        limite = reto["celdas"] if juego == "memoria" else reto["cantidad"]
        if not isinstance(respuesta, int) or not 0 <= respuesta < limite:
            return
        secuencia = progreso["secuencia"]
        # Ronda cerrada (completa o, en memoria, fallada): no se aceptan más toques.
        if respuesta in secuencia or progreso.get("fin") is not None:
            return
        if juego == "menor":
            if not secuencia:
                progreso["total"] = len(reto["numeros"])
            esperado = reto["orden"][len(secuencia)]
            acepta = respuesta == esperado
            if acepta:
                secuencia.append(respuesta)
            else:
                progreso["fallos"] += 1
            await _feedback_privado(sala, jugador, juego, acepta)
            if len(secuencia) == len(reto["numeros"]):
                progreso["fin"] = ahora
                sala.respuestas[jugador.id] = (secuencia, ahora)
        else:  # memoria: un error cierra la ronda como fallida
            if not secuencia:
                progreso["total"] = reto["cantidad"]
            esperado = reto["posiciones"][str(len(secuencia) + 1)]
            acepta = respuesta == esperado
            if acepta:
                secuencia.append(respuesta)
            else:
                progreso["fallos"] += 1
            await _feedback_privado(sala, jugador, juego, acepta)
            if len(secuencia) == reto["cantidad"] or not acepta:
                progreso["fin"] = ahora
                sala.respuestas[jugador.id] = (secuencia, ahora)
    else:
        if jugador.id in sala.respuestas:
            return
        progreso["total"] = 1
        if juego == "stroop":
            acepta = respuesta == reto["correcta"]
            if not acepta:
                progreso["fallos"] += 1
            await _feedback_privado(sala, jugador, juego, acepta)
        elif juego == "vuelto":
            if not isinstance(respuesta, dict):
                return
            # Solo billetes/monedas reales y cantidades no negativas: evita
            # cuadrar el vuelto con cantidades negativas o claves gigantes.
            validas = {str(d) for d in DENOMINACIONES_CLP}
            if not all(
                clave in validas
                and isinstance(cantidad, int)
                and not isinstance(cantidad, bool)
                and 0 <= cantidad <= 100
                for clave, cantidad in respuesta.items()
            ):
                respuesta = {}
            total = sum(int(clave) * cantidad for clave, cantidad in respuesta.items())
            acepta = total == reto["vuelto"]
            optimo = acepta and all(
                respuesta.get(clave, 0) == cantidad
                for clave, cantidad in reto["optimo"].items()
            )
            if not acepta:
                progreso["fallos"] += 1
            progreso["optimo"] = optimo
            progreso["total_entregado"] = total
            await _feedback_privado(sala, jugador, juego, acepta, optimo=optimo)
        elif juego == "relojes":
            if not isinstance(respuesta, dict):
                return
            horas = respuesta.get("horas")
            minutos = respuesta.get("minutos")
            if not isinstance(horas, int) or not isinstance(minutos, int):
                return
            entregado = f"{horas:02d}{minutos:02d}"
            acepta = entregado == reto["esperado"]
            if not acepta:
                progreso["fallos"] += 1
            await _feedback_privado(sala, jugador, juego, acepta)
        elif juego == "silabas":
            if not isinstance(respuesta, int):
                return
            acepta = respuesta == reto["total"]
            if not acepta:
                progreso["fallos"] += 1
            await _feedback_privado(sala, jugador, juego, acepta)
        elif juego == "ppt":
            # Solo se acepta una mano válida (en minúsculas); el rival nunca
            # coincide con la mano correcta, así que empatar cuenta como error.
            if respuesta not in MANOS:
                return
            acepta = respuesta == reto["esperado"]
            if not acepta:
                progreso["fallos"] += 1
            await _feedback_privado(sala, jugador, juego, acepta)
        else:
            return
        progreso["fin"] = ahora
        sala.respuestas[jugador.id] = (respuesta, ahora)

    if len(sala.respuestas) >= len(participantes(sala)):
        sala.evento_respuestas.set()


async def bucle_minijuego(sala: Sala, juego: str) -> None:
    """Instrucciones → cuenta regresiva → rondas → resultados, como los demás."""
    jugadores_ = participantes(sala)
    ids = [j.id for j in jugadores_]
    tiempos = {pid: 0.0 for pid in ids}
    fallos = {pid: 0 for pid in ids}
    aciertos = {pid: 0 for pid in ids}
    brain_age_ronda = {pid: 0.0 for pid in ids}
    anterior = None
    sala.ultimos_brain_age = {}
    total_rondas = rondas_para(sala, RONDAS_MINI[juego])
    espera = TIEMPO_RESPUESTA_MINI[juego]

    try:
        await nucleo.pausa(sala, 0.6)
        if sala.cancelada:
            return
        sala.fase = juego
        await sala.difundir(
            {
                "type": "match_start",
                "modo": juego,
                "marcador": marcador_mini(sala, juego, brain_age_ronda, 0),
            }
        )

        for ronda in range(1, total_rondas + 1):
            if sala.cancelada:
                return
            # La dificultad de fiesta adelanta la ronda que ve el generador;
            # el reto viaja con la ronda real para validar las respuestas.
            ronda_gen = ronda_generador(sala, ronda, (0, 3, 7))
            reto = generar(ronda_gen, juego, anterior)
            reto["ronda"] = ronda
            if "necesario" in reto:
                reto["necesario"] = total_rondas
            anterior = (
                reto.get("clave") if juego == "stroop"
                else reto.get("frase") if juego == "silabas"
                else None
            )
            sala.datos = {
                "juego": juego,
                "ronda": ronda,
                "reto": reto,
                "momento_respuesta": None,
                "escribiendo": juego in JUEGOS_ESCRITURA,
            }
            sala.respuestas = {}
            sala.evento_respuestas.clear()
            sala.evento_escritura.clear()

            if juego in JUEGOS_ESCRITURA:
                for jugador in jugadores_:
                    jugador.progreso = {
                        "esperado": reto["esperado"],
                        "digitos": [
                            {"intentos": 0, "estado": "pendiente", "motivo": ""}
                            for _ in reto["esperado"]
                        ],
                        "inicio": None,
                        "fin": None,
                        "fallos": 0,
                    }
            else:
                for jugador in jugadores_:
                    jugador.progreso = {
                        "secuencia": [], "fallos": 0, "total": 0,
                        "inicio": None, "fin": None,
                    }

            if sala.modo == "fiesta":
                await emitir_progreso_vivo(
                    sala, juego, filas_avance_mini(sala, juego), ronda
                )

            await sala.difundir(
                {
                    "type": f"{juego}_countdown",
                    "segundos": TIEMPO_CUENTA_MINI,
                    "ronda": ronda,
                    "necesario": total_rondas,
                    "dificultad": reto.get("dificultad", ""),
                    "marcador": marcador_mini(sala, juego, brain_age_ronda, ronda),
                }
            )
            await nucleo.pausa(sala, TIEMPO_CUENTA_MINI)
            if sala.cancelada:
                return

            completo = {"type": f"{juego}_show", "ronda": ronda, **reto}
            for secreto in SECRETOS_MINI[juego]:
                completo.pop(secreto, None)
            para_mandos = {
                "type": f"{juego}_show",
                "ronda": ronda,
                "dificultad": reto.get("dificultad", ""),
                **estimulo_para_mando(juego, reto),
            }
            exposicion = None
            if juego == "memoria":
                completo["duracion"] = reto["segundos"]
                para_mandos["duracion"] = reto["segundos"]
            elif juego == "stroop":
                exposicion = exposicion_stroop(ronda_gen)
                completo["duracion"] = exposicion
                para_mandos["duracion"] = exposicion
            await difundir_roles(sala, completo, para_mandos)

            if juego in ("memoria", "stroop"):
                # La exposición no cuenta para el Brain Age: se cronometra desde
                # que la palabra (o la grilla) desaparece.
                duracion = reto["segundos"] if juego == "memoria" else exposicion
                await nucleo.pausa(sala, duracion)
                if sala.cancelada:
                    return
                sala.datos["momento_respuesta"] = time.monotonic()
                hide = {"type": f"{juego}_hide", "ronda": ronda}
                if juego == "memoria":
                    hide["grilla"] = reto["grilla"]
                await sala.difundir(hide)
            else:
                sala.datos["momento_respuesta"] = time.monotonic()

            datos_write: dict = {}
            datos_mando: dict = {}
            if juego in MINIJUEGOS_SOLO_PANTALLA:
                # La pantalla sigue dibujando el estímulo mientras se responde,
                # salvo en Stroop: la palabra ya se borró con el _hide.
                if juego != "stroop":
                    datos_write.update(visual_mini(juego, reto))
                datos_mando["mira"] = True

            if juego == "menor":
                datos_write = {"numeros": reto["numeros"]}
                datos_mando = dict(datos_write)
            elif juego == "memoria":
                datos_write = {
                    "grilla": reto["grilla"],
                    "celdas": reto["celdas"],
                    "cantidad": reto["cantidad"],
                }
                datos_mando = dict(datos_write)
            elif juego == "vuelto":
                datos_write["denominaciones"] = reto["denominaciones"]
                datos_mando["denominaciones"] = reto["denominaciones"]
            elif juego in JUEGOS_ESCRITURA:
                comunes = {
                    "digitos": len(reto["esperado"]),
                    "campo": {
                        "triangulos": "RESULTADO FINAL",
                        "relojes": "HORAS Y MINUTOS",
                        "silabas": "NÚMERO DE SÍLABAS",
                    }[juego],
                }
                datos_write.update(comunes)
                datos_write["estimulo"] = visual_mini(juego, reto)
                # El celular escribe el resultado mirando la PC: sin pirámide.
                datos_mando.update(comunes)
            base_write = {
                "type": f"{juego}_write",
                "ronda": ronda,
                "marcador": marcador_mini(sala, juego, brain_age_ronda, ronda),
            }
            await difundir_roles(
                sala,
                {**base_write, **datos_write},
                {**base_write, **datos_mando},
            )

            if juego in JUEGOS_ESCRITURA:
                await esperar(sala, sala.evento_escritura, espera)
            else:
                await esperar(sala, sala.evento_respuestas, espera)
            if sala.cancelada:
                return

            momento = sala.datos["momento_respuesta"]
            ahora = time.monotonic()
            por_jugador: dict[str, dict] = {}
            for jugador in jugadores_:
                pid = jugador.id
                progreso = jugador.progreso
                respuesta = sala.respuestas.get(pid)
                if juego in JUEGOS_ESCRITURA:
                    acierto = all(
                        casilla["estado"] == "aceptada"
                        for casilla in progreso["digitos"]
                    )
                    # Sin respuesta: el plazo completo y un error.
                    errores = progreso["fallos"] + (0 if progreso["fin"] else 1)
                    fin = progreso["fin"] or ahora
                else:
                    respuesta = sala.respuestas.get(pid)
                    if juego == "menor":
                        acierto = len(progreso["secuencia"]) == len(reto["numeros"])
                    elif juego == "memoria":
                        acierto = len(progreso["secuencia"]) == reto["cantidad"]
                    elif juego == "stroop":
                        acierto = bool(respuesta) and respuesta[0] == reto["correcta"]
                    elif juego == "silabas":
                        acierto = bool(respuesta) and respuesta[0] == reto["total"]
                    elif juego == "relojes":
                        reto_esperado = reto["esperado"]
                        if respuesta:
                            entregado = f"{respuesta[0].get('horas', 0):02d}{respuesta[0].get('minutos', 0):02d}"
                            acierto = entregado == reto_esperado
                        else:
                            acierto = False
                    elif juego == "ppt":
                        acierto = bool(respuesta) and respuesta[0] == reto["esperado"]
                    else:
                        acierto = bool(respuesta) and progreso.get("total_entregado") == reto["vuelto"]
                    # Sin respuesta: el plazo completo y un error.
                    errores = progreso["fallos"] + (0 if respuesta else 1)
                    fin = progreso["fin"] or ahora
                if not respuesta and juego not in JUEGOS_ESCRITURA:
                    tiempo = espera
                else:
                    tiempo = max(0.0, fin - momento)
                if acierto:
                    aciertos[pid] += 1
                fallos[pid] += errores
                tiempos[pid] += tiempo
                brain_age_ronda[pid] = brain_age(tiempos[pid], fallos[pid])
                por_jugador[pid] = {
                    "acierto": acierto,
                    "errores": errores,
                    "tiempo": round(tiempo, 2),
                    "brain_age": round(brain_age_ronda[pid], 2),
                }

            principal = por_jugador[ids[0]] if ids else {}
            # El informe se ve solo en la pantalla: al mando no le llega la
            # respuesta correcta ni el desglose de la ronda.
            await difundir_roles(
                sala,
                {
                    "type": f"{juego}_result",
                    "ronda": ronda,
                    "necesario": total_rondas,
                    "dificultad": reto.get("dificultad", ""),
                    "reto": datos_para_resultado(juego, reto),
                    "jugadores": por_jugador,
                    "clasificacion": clasificacion(sala),
                    "marcador": marcador_mini(sala, juego, brain_age_ronda, ronda),
                    **principal,
                },
                {"type": f"{juego}_result", "ronda": ronda},
            )
            await nucleo.pausa(sala, 2.5 if ronda < total_rondas else 1.0)

        pid = ids[0] if ids else sala.host_id
        brain = brain_age(tiempos.get(pid, 0.0), fallos.get(pid, 0))
        precision = 100 * aciertos.get(pid, 0) / total_rondas
        promedio = tiempos.get(pid, 0.0) / total_rondas
        resumen = {
            "rondas": total_rondas,
            "aciertos": aciertos.get(pid, 0),
            "errores": fallos.get(pid, 0),
            "brain_age": round(brain, 2),
            "precision": round(precision, 1),
            "tiempo_promedio": round(promedio, 2),
            "tiempo_total": round(tiempos.get(pid, 0.0), 2),
        }

        if sala.secuencia_individual:
            sala.resultados_individual[juego] = resumen
            return

        sala.fase = "fin"
        sala.ultimos_brain_age = dict(brain_age_ronda)
        await sala.difundir(
            {
                "type": f"{juego}_over",
                "nombre": sala.jugadores[pid].nombre if pid in sala.jugadores else "JUGADOR",
                "clasificacion": [
                    {
                        "id": jugador.id,
                        "nombre": jugador.nombre,
                        "brain_age": round(brain_age_ronda[jugador.id], 2),
                    }
                    for jugador in jugadores_
                ],
                **resumen,
            }
        )
    except asyncio.CancelledError:
        raise
