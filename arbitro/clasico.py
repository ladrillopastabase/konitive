"""Duelo clásico: HÁMSTERS y PALABRAS al mejor de 3, y su árbitro de escritura."""
from __future__ import annotations

import asyncio
import random
import time
import uuid

from juego.palabras import palabra_para
from arbitro import nucleo
from arbitro.puntuacion import brain_age_y_puntos, fallos_escritura, sumar_historial
from arbitro.nucleo import (
    JUEGOS,
    Jugador,
    RONDAS_FIESTA,
    Sala,
    TIEMPO_CUENTA_PREVIA,
    VICTORIAS_NECESARIAS,
    decidir_ganador,
    difundir_roles,
    emitir_progreso_vivo,
    elegir_juego,
    filas_avance_escritura,
    esperar,
    ganador_de_juego,
    nombre_de,
    participantes,
    reconocer_en_hilo,
    registrar_resultado_individual,
    ronda_generador,
    rondas_para,
    trazos_validos,
)


CANTIDADES_PAJAROS = (5, 8, 11, 14, 18)
# Niveles que se adelantan en fiesta con dificultad (fácil, normal, difícil):
# hay 5 niveles de aves y de largo de palabra.
SALTOS_DIFICULTAD = (0, 1, 3)
# Probabilidad de que cada hámster dé saltitos. Desde el primer nivel saltan
# algunos (nunca todos) y cada nivel suma más saltarines.
PROBABILIDAD_SALTO = (0.35, 0.4, 0.45, 0.5, 0.6)
TIEMPO_ESPERA_RESPUESTA = 25
TIEMPO_ESPERA_ESCRITURA = 120
TIEMPO_FLASH_PALABRA = 0.8
PUNTOS_LETRA = {"primera": 30, "posterior": 20, "automatica": 10}
PUNTOS_DIGITO = {"primera": 30, "posterior": 20, "automatica": 10}


def generar_pajaros(nivel: int) -> list[dict]:
    """Aves quietas o con saltitos cortos y desplazamiento mínimo."""
    cantidad = CANTIDADES_PAJAROS[min(nivel - 1, len(CANTIDADES_PAJAROS) - 1)]
    probabilidad = PROBABILIDAD_SALTO[min(nivel - 1, len(PROBABILIDAD_SALTO) - 1)]
    aves: list[dict] = []
    # Niveles 1-3: hámsters grandes y pocos; desde el 4, más chicos y juntos.
    separacion = 0.16 if nivel <= 3 else 0.12
    for i in range(cantidad):
        # Separación por eje: los hámsters son cuadrados y no deben encimarse.
        for _ in range(200):
            x, y = random.uniform(0.08, 0.92), random.uniform(0.14, 0.86)
            if all(max(abs(x - a["x"]), abs(y - a["y"])) > separacion for a in aves):
                break
        salta = random.random() < probabilidad
        aves.append(
            {
                "id": i,
                "x": round(x, 4),
                "y": round(y, 4),
                "size": random.randint(26, 44) if nivel <= 3 else random.randint(24, 34),
                "salta": salta,
                "periodo": round(random.uniform(1.1, 1.8), 2) if salta else 0,
                "fase": round(random.uniform(0, 1.4), 2) if salta else 0,
                "duracion": round(random.uniform(0.2, 0.34), 2) if salta else 0,
                "dx": round(random.uniform(-0.03, 0.03), 3) if salta else 0,
                "dy": round(random.uniform(-0.018, 0.018), 3) if salta else 0,
                "altura": random.randint(12, 24) if salta else 0,
            }
        )
    return aves


def estado_conteos(sala: Sala) -> dict:
    """Instantánea de lo que cada jugador está contando y quién confirmó."""
    return {
        "conteos": dict(sala.conteos_vivos),
        "confirmados": sorted(sala.conteos_confirmados),
    }


def estado_avance_pajaros(sala: Sala) -> list[dict]:
    """Cuenta de cada mando para la pantalla, sin revelar cuántos hay."""
    return [
        {
            "id": jugador.id,
            "nombre": jugador.nombre,
            "avance": sala.conteos_vivos.get(jugador.id, 0),
            "total": None,
            "estado": (
                "listo"
                if jugador.id in sala.conteos_confirmados
                else "contando"
                if jugador.id in sala.conteos_vivos
                else "esperando"
            ),
        }
        for jugador in participantes(sala)
    ]


async def difundir_conteos(sala: Sala) -> None:
    if sala.modo == "fiesta":
        # En fiesta la cuenta ajena solo se proyecta; el celular no la recibe.
        await emitir_progreso_vivo(
            sala, "pajaros", estado_avance_pajaros(sala), sala.datos.get("nivel")
        )
    else:
        await sala.difundir({"type": "bird_tally", **estado_conteos(sala)})


async def ronda_pajaros(sala: Sala, nivel: int) -> dict[str, int]:
    aves = generar_pajaros(nivel)
    # Fase de observación (la barrita). Los hámsters siguen visibles después.
    duracion = 6.0 if nivel <= 2 else 5.0
    # Tiempo total para responder: observación + respuesta (lo que muestra la barrita).
    limite = duracion + TIEMPO_ESPERA_RESPUESTA
    sala.datos.update({"esperado": len(aves), "aves": aves, "nivel": nivel})
    sala.respuestas = {}
    sala.conteos_vivos = {j.id: 0 for j in participantes(sala)}
    sala.conteos_confirmados = set()
    sala.evento_respuestas.clear()

    # Cuenta previa sin aves ni contador; la observación empieza después.
    await sala.difundir({"type": "birds_countdown", "segundos": TIEMPO_CUENTA_PREVIA})
    await nucleo.pausa(sala, TIEMPO_CUENTA_PREVIA)
    if sala.cancelada:
        return {}

    sala.datos["momento_respuesta"] = time.monotonic()
    sala.datos["conteo_token"] = uuid.uuid4().hex
    token = sala.datos["conteo_token"]
    await difundir_roles(
        sala,
        {
            "type": "birds_show",
            "aves": aves,
            "duracion": duracion,
            "limite": limite,
            "nivel": nivel,
            "marcador": sala.marcador(),
            "token": token,
        },
        # Los mandos de la fiesta miran la pantalla: no reciben las aves.
        {"type": "birds_show", "duracion": duracion, "limite": limite, "nivel": nivel, "token": token},
    )
    if sala.modo == "fiesta":
        await emitir_progreso_vivo(
            sala, "pajaros", estado_avance_pajaros(sala), nivel
        )
    # Las aves se ven durante toda la fase de observación; el cliente las deja
    # en pantalla mientras se cuenta, y el éxito se mide por el tiempo.
    await nucleo.pausa(sala, duracion)
    await sala.difundir(
        {
            "type": "birds_hide",
            "segundos": TIEMPO_ESPERA_RESPUESTA,
            **estado_conteos(sala),
            "token": token,
        }
    )
    await esperar(sala, sala.evento_respuestas, TIEMPO_ESPERA_RESPUESTA)

    momento = sala.datos["momento_respuesta"]
    tiempos: dict[str, float] = {}
    errores: dict[str, int] = {}
    brains: dict[str, float] = {}
    puntos: dict[str, int] = {}
    desglose: dict[str, dict] = {}
    for jugador in participantes(sala):
        pid = jugador.id
        respuesta = sala.respuestas.get(pid)
        if respuesta is None:
            tiempo = float(TIEMPO_ESPERA_RESPUESTA)
            fallos = 1
        else:
            conteo, instante = respuesta
            tiempo = max(0.0, instante - momento)
            fallos = 0 if conteo == sala.datos["esperado"] else 1
        brain, puntos[pid] = sumar_historial(
            sala.historial.get("pajaros", []), pid, tiempo, fallos
        )
        tiempos[pid] = tiempo
        errores[pid] = fallos
        brains[pid] = brain
        desglose[pid] = {
            "tiempo": tiempo,
            "errores": fallos,
            "brain_age": brain,
            "total": puntos[pid],
        }
    sala.datos.update(
        {"tiempo": tiempos, "errores": errores, "brain_age": brains, "desglose": desglose}
    )
    return puntos


async def ronda_escritura(sala: Sala, nivel: int) -> dict[str, int]:
    """Cuenta 3 s, muestra la palabra un instante y después deja escribir.

    Durante la escritura el cliente no recibe la palabra ni cuántas letras le
    faltan: solo ve las letras que ya ha conseguido. La puntuación se calcula
    aquí y se guarda el desglose para que el resultado sea transparente.
    """
    palabra = palabra_para(nivel, sala.usadas)
    sala.usadas.add(palabra)
    sala.datos["palabra"] = palabra
    sala.datos["escribiendo"] = False
    sala.datos["desglose"] = {}
    sala.datos["nivel"] = nivel
    sala.evento_escritura.clear()

    for jugador in participantes(sala):
        jugador.progreso = {
            "palabra": palabra,
            "letras": [
                {"intentos": 0, "puntos": 0, "estado": "pendiente", "motivo": ""}
                for _ in palabra
            ],
            "inicio": None,
            "fin": None,
        }

    if sala.modo == "fiesta":
        await emitir_progreso_vivo(
            sala,
            "escritura",
            filas_avance_escritura(sala, "escritura", "letras", "palabra"),
            sala.datos.get("ronda"),
        )

    await sala.difundir(
        {
            "type": "word_countdown",
            "segundos": TIEMPO_CUENTA_PREVIA,
            "nivel": nivel,
            "marcador": sala.marcador(),
        }
    )
    await nucleo.pausa(sala, TIEMPO_CUENTA_PREVIA)
    if sala.cancelada:
        return {}

    await difundir_roles(
        sala,
        {
            "type": "word_show",
            "palabra": palabra,
            "nivel": nivel,
            "flash": TIEMPO_FLASH_PALABRA,
            "marcador": sala.marcador(),
        },
        # La palabra solo está en la pantalla; el mando debe memorizarla de ahí.
        {
            "type": "word_show",
            "nivel": nivel,
            "flash": TIEMPO_FLASH_PALABRA,
            "marcador": sala.marcador(),
        },
    )
    await nucleo.pausa(sala, TIEMPO_FLASH_PALABRA)
    if sala.cancelada:
        return {}

    inicio = time.monotonic()
    for jugador in participantes(sala):
        jugador.progreso["inicio"] = inicio
    sala.datos["escribiendo"] = True
    await sala.difundir(
        {
            "type": "word_write",
            "nivel": nivel,
            "marcador": sala.marcador(),
        }
    )

    await esperar(sala, sala.evento_escritura, TIEMPO_ESPERA_ESCRITURA)

    puntos: dict[str, int] = {}
    desglose: dict[str, dict] = {}
    tiempos: dict[str, float] = {}
    errores: dict[str, int] = {}
    brains: dict[str, float] = {}
    for jugador in participantes(sala):
        progreso = jugador.progreso
        if not progreso or progreso.get("inicio") is None:
            tiempo = float(TIEMPO_ESPERA_ESCRITURA)
            fallos = 1
            correctas = 0
            automaticas = 0
        else:
            fin = progreso.get("fin")
            tiempo = (
                max(0.0, fin - progreso["inicio"])
                if fin is not None
                else float(TIEMPO_ESPERA_ESCRITURA)
            )
            fallos = fallos_escritura(progreso["letras"], incompleto=fin is None)
            correctas = sum(
                1 for letra in progreso["letras"] if letra["motivo"] != "automatica"
            )
            automaticas = sum(
                1 for letra in progreso["letras"] if letra["motivo"] == "automatica"
            )

        pid = jugador.id
        brain, puntos[pid] = sumar_historial(
            sala.historial.get("escritura", []), pid, tiempo, fallos
        )
        tiempos[pid] = tiempo
        errores[pid] = fallos
        brains[pid] = brain
        desglose[pid] = {
            "tiempo": tiempo,
            "errores": fallos,
            "brain_age": brain,
            "total": puntos[pid],
            "correctas": correctas,
            "automaticas": automaticas,
        }

    sala.datos.update(
        {"tiempo": tiempos, "errores": errores, "brain_age": brains, "desglose": desglose}
    )
    return puntos


def _brain_age_acumulado(sala: Sala, juego: str, pid: str) -> tuple[float, int, float]:
    tiempo = sum(
        entrada.get("tiempo", {}).get(pid, 0.0)
        for entrada in sala.historial.get(juego, [])
    )
    errores = sum(
        entrada.get("errores", {}).get(pid, 0)
        for entrada in sala.historial.get(juego, [])
    )
    brain, _ = brain_age_y_puntos(tiempo, errores)
    return tiempo, errores, brain


def resumen_clasico_individual(sala: Sala, juego: str) -> dict:
    """Resultado de HÁMSTERS o PALABRAS dentro de la secuencia individual."""
    pid = next(iter(sala.jugadores), sala.host_id)
    puntos = [entrada["puntos"].get(pid, 0) for entrada in sala.historial[juego]]
    tiempo, errores, brain = _brain_age_acumulado(sala, juego, pid)
    return {
        "rondas": sala.rondas_juego[juego],
        "victorias": sala.ganadas[juego].get(pid, 0),
        "mejor": max(puntos, default=0),
        "total": sum(puntos),
        "puntos": sum(puntos),
        "tiempo_total": tiempo,
        "errores": errores,
        "brain_age": brain,
    }


async def enviar_resumen_practica(sala: Sala) -> None:
    """Entrega un informe de la tanda de práctica y espera a seguir o salir."""
    pid = next(iter(sala.jugadores), sala.host_id)
    resumen: dict[str, dict] = {}
    for juego in JUEGOS:
        puntos = [
            entrada["puntos"].get(pid, 0) for entrada in sala.historial[juego]
        ]
        tiempo, errores, brain = _brain_age_acumulado(sala, juego, pid)
        resumen[juego] = {
            "rondas": sala.rondas_juego[juego],
            "victorias": sala.ganadas[juego].get(pid, 0),
            "mejor": max(puntos, default=0),
            "total": sum(puntos),
            "tiempo_total": tiempo,
            "errores": errores,
            "brain_age": brain,
        }

    sala.fase = "resumen"
    sala.evento_continuar.clear()
    await sala.difundir(
        {
            "type": "practice_summary",
            "resumen": resumen,
            "marcador": sala.marcador(),
            "nombre": nombre_de(sala, pid),
            "necesario": VICTORIAS_NECESARIAS,
        }
    )
    # Sin límite de tiempo: la persona decide cuándo seguir o sale con SALIR.
    await esperar(sala, sala.evento_continuar, None)


async def terminar_partida(sala: Sala, ganador: str | None) -> None:
    sala.fase = "fin"
    nombres = {pid: j.nombre for pid, j in sala.jugadores.items()}
    await sala.difundir(
        {
            "type": "match_over",
            "ganador": ganador,
            "nombre_ganador": nombres.get(ganador, "nadie"),
            "marcador": sala.marcador(),
        }
    )


async def bucle_partida(sala: Sala) -> None:
    try:
        await nucleo.pausa(sala, 0.6)
        await sala.difundir(
            {
                "type": "match_start",
                "marcador": sala.marcador(),
                "practica": sala.practica,
                "modo": sala.modo,
                "juego_fiesta": sala.juego_fiesta,
            }
        )

        while not sala.cancelada:
            juego = elegir_juego(sala)
            if juego is None:
                if sala.secuencia_individual:
                    registrar_resultado_individual(
                        sala, sala.juego_individual, resumen_clasico_individual(sala, sala.juego_individual)
                    )
                    return
                if sala.practica:
                    # En práctica no hay campeón: se entrega el informe y se
                    # puede seguir entrenando con el marcador reiniciado.
                    await enviar_resumen_practica(sala)
                    if sala.cancelada:
                        return
                    sala.reiniciar_marcador()
                    sala.fase = "jugando"
                    continue
                await terminar_partida(sala, None)
                return

            sala.rondas_juego[juego] += 1
            nivel = sala.rondas_juego[juego]
            sala.fase = "desempate" if sala.desempate else juego
            sala.datos = {
                "juego": juego,
                "nivel": nivel,
                "desempate": sala.desempate,
            }
            sala.puntos = {}

            await sala.difundir(
                {
                    "type": "round_start",
                    "juego": juego,
                    "nivel": nivel,
                    "desempate": sala.desempate,
                    "marcador": sala.marcador(),
                }
            )

            # La dificultad de fiesta adelanta el nivel de aves y palabras.
            nivel_reto = ronda_generador(sala, nivel, SALTOS_DIFICULTAD)
            if juego == "pajaros":
                puntos = await ronda_pajaros(sala, nivel_reto)
            else:
                puntos = await ronda_escritura(sala, nivel_reto)
            if sala.cancelada:
                return

            ganador = decidir_ganador(puntos)
            if sala.desempate:
                if ganador is None:
                    ganador = random.choice([j.id for j in participantes(sala)])
                await terminar_partida(sala, ganador)
                return

            if ganador is not None:
                sala.ganadas[juego][ganador] = sala.ganadas[juego].get(ganador, 0) + 1
            sala.ultimo_juego = juego
            sala.historial[juego].append(
                {
                    "nivel": nivel,
                    "puntos": dict(puntos),
                    "tiempo": dict(sala.datos.get("tiempo", {})),
                    "errores": dict(sala.datos.get("errores", {})),
                    "brain_age": dict(sala.datos.get("brain_age", {})),
                    "esperado": sala.datos.get("esperado"),
                    "palabra": sala.datos.get("palabra"),
                    "ganador": ganador,
                }
            )

            # Cada mando recibe solo su acierto; el informe con la respuesta
            # correcta se queda en la pantalla.
            desglose_ronda = sala.datos.get("desglose", {})
            for jugador in participantes(sala):
                if juego == "pajaros":
                    acepta = sala.datos.get("errores", {}).get(jugador.id, 1) == 0
                else:
                    acepta = desglose_ronda.get(jugador.id, {}).get("correctas", 0) > 0
                await jugador.enviar(
                    {
                        "type": "round_feedback",
                        "pid": jugador.id,
                        "juego": juego,
                        "acepta": acepta,
                        "ronda": sala.datos.get("ronda", 0),
                    }
                )

            # En FIESTA el informe se ve solo en la pantalla: al mando no le
            # llega la palabra ni el recuento correcto de la ronda.
            await difundir_roles(
                sala,
                {
                    "type": "round_result",
                    "juego": juego,
                    "nivel": nivel,
                    "puntos": puntos,
                    "esperado": sala.datos.get("esperado"),
                    "palabra": sala.datos.get("palabra"),
                    "desglose": sala.datos.get("desglose", {}),
                    "ganador": ganador,
                    "marcador": sala.marcador(),
                    "desempate": False,
                    "practica": sala.practica,
                },
                {"type": "round_result", "nivel": nivel},
            )
            await nucleo.pausa(sala, 4.0 if not sala.practica else 2.0)
            if sala.cancelada:
                return

            if sala.practica:
                # Se alternan minijuegos hasta completar la tanda; entonces se
                # muestra el resumen y se ofrece seguir entrenando.
                continue

            if sala.juego_fiesta:
                # Antes se cortaba tras la primera ronda: ahora se juegan las
                # rondas elegidas en el lobby y gana quien sume más puntos.
                if nivel < rondas_para(sala, RONDAS_FIESTA):
                    continue
                sala.ultimos_puntos = {
                    j.id: sum(
                        entrada["puntos"].get(j.id, 0)
                        for entrada in sala.historial[sala.juego_fiesta]
                    )
                    for j in participantes(sala)
                }
                await terminar_partida(sala, decidir_ganador(sala.ultimos_puntos))
                return

            for otro in JUEGOS:
                campeon = ganador_de_juego(sala, otro)
                if campeon and otro not in sala.anunciados:
                    sala.anunciados.add(otro)
                    await sala.difundir(
                        {
                            "type": "minigame_result",
                            "juego": otro,
                            "ganador": campeon,
                            "nombre": nombre_de(sala, campeon),
                            "marcador": sala.marcador(),
                        }
                    )
                    await nucleo.pausa(sala, 3.0)
                    if sala.cancelada:
                        return

            campeones = {j: ganador_de_juego(sala, j) for j in JUEGOS}
            if all(campeones.values()):
                if campeones["pajaros"] == campeones["escritura"]:
                    await terminar_partida(sala, campeones["pajaros"])
                    return
                sala.desempate = True
                sala.juego_desempate = random.choice(JUEGOS)
                await sala.difundir(
                    {
                        "type": "tiebreak_start",
                        "juego": sala.juego_desempate,
                        "mensaje": "¡Empate! Ronda de desempate al azar",
                    }
                )
                await nucleo.pausa(sala, 3.5)
    except asyncio.CancelledError:
        pass


# Escritura a mano: PALABRAS (letras) y OPERACIONES (cifras) comparten árbitro.
ESCRITURA = {
    "letter": {
        "fase": "escritura",
        "casillas": "letras",
        "esperado": "palabra",
        # lambda: se resuelve al llamar, para poder sustituir el modelo en pruebas.
        "reconocer": lambda trazos: nucleo.reconocedor.reconocer(trazos),
        "puntos": PUNTOS_LETRA,
        "feedback": "letter_feedback",
        "hecho": "word_done",
    },
    "digit": {
        "fase": "operaciones",
        "casillas": "digitos",
        "esperado": "resultado",
        "reconocer": lambda trazos: nucleo.reconocedor_digitos.reconocer(trazos),
        "puntos": PUNTOS_DIGITO,
        "feedback": "digit_feedback",
        "hecho": "operacion_done",
    },
}


async def procesar_caracter(sala: Sala, jugador: Jugador, mensaje: dict, cfg: dict) -> None:
    """Reconoce una letra o cifra manuscrita; a los 3 intentos se acepta sola."""
    progreso = jugador.progreso
    indice = mensaje.get("index")
    if (
        not progreso
        or sala.fase not in (cfg["fase"], "desempate")
        or not sala.datos.get("escribiendo")
        or not isinstance(indice, int)
        or not 0 <= indice < len(progreso[cfg["esperado"]])
        or (sala.modo == "fiesta" and jugador.rol != "mando")
    ):
        return

    casillas = progreso[cfg["casillas"]]
    estado = casillas[indice]
    if estado["estado"] == "aceptada" or estado.get("procesando"):
        return

    limpios = trazos_validos(mensaje)
    if not limpios:
        return

    esperada = progreso[cfg["esperado"]][indice]
    predicha, confianza = await reconocer_en_hilo(cfg["reconocer"], limpios, estado)
    # Mientras se reconocía pudo cerrarse la ronda o empezar otra.
    if jugador.progreso is not progreso or not sala.datos.get("escribiendo"):
        return
    estado["intentos"] += 1

    if predicha == esperada:
        tipo_punto = "primera" if estado["intentos"] == 1 else "posterior"
        estado["estado"] = "aceptada"
        motivo = "correcta"
    elif estado["intentos"] >= 3:
        tipo_punto = "automatica"
        estado["estado"] = "aceptada"
        motivo = "aceptada por intentos"
    else:
        tipo_punto = ""
        motivo = "inténtalo otra vez"
    puntos = cfg["puntos"].get(tipo_punto, 0)
    estado["puntos"] = puntos
    estado["motivo"] = tipo_punto

    await jugador.enviar(
        {
            "type": cfg["feedback"],
            "index": indice,
            "esperada": esperada,
            "predicha": predicha,
            "confianza": round(confianza, 2),
            "intentos": estado["intentos"],
            "aceptada": estado["estado"] == "aceptada",
            "puntos": puntos,
            "motivo": motivo,
        }
    )

    if sala.modo == "fiesta":
        await emitir_progreso_vivo(
            sala,
            cfg["fase"],
            filas_avance_escritura(
                sala, cfg["fase"], cfg["casillas"], cfg["esperado"]
            ),
            sala.datos.get("ronda"),
        )

    if all(c["estado"] == "aceptada" for c in casillas):
        progreso["fin"] = time.monotonic()
        await jugador.enviar(
            {
                "type": cfg["hecho"],
                "puntos": sum(c["puntos"] for c in casillas),
                "automaticas": sum(1 for c in casillas if c["motivo"] == "automatica"),
            }
        )
        if all(j.progreso.get("fin") is not None for j in participantes(sala)):
            sala.evento_escritura.set()
