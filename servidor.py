"""Servidor de Konitive: salas, sincronización y árbitro de los minijuegos.

Arrancar con::

    uvicorn servidor:app --host 0.0.0.0 --port 8000

o directamente::

    python servidor.py
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import random
import socket
import string
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import qrcode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from qrcode.image.svg import SvgPathImage

from juego.cajas import DIFICULTADES, generar_pila
from juego.minijuegos import (
    JUEGOS_ESCRITURA,
    JUEGOS_MINI,
    NOMBRES_MINI,
    RONDAS_MINI,
    generar,
)
from juego.operaciones import generar_operacion
from juego.palabras import palabra_para
from juego.reconocedor import Reconocedor, ReconocedorDigitos

BASE = Path(__file__).parent
ESTATICO = BASE / "static"

JUEGOS = ("pajaros", "escritura")
# Fiesta: los juegos clásicos más los siete minijuegos de entrenamiento.
# El host es la pantalla y hay hasta 8 mandos.
JUEGOS_FIESTA = ("pajaros", "escritura", "cajas", "operaciones") + JUEGOS_MINI
NOMBRES_JUEGOS = {
    "pajaros": "PÁJAROS",
    "escritura": "PALABRAS",
    "cajas": "CAJAS",
    "operaciones": "OPERACIONES",
    **NOMBRES_MINI,
}
MAX_MANDOS = 8
TIEMPO_PODIO = 4.5
VICTORIAS_NECESARIAS = 3
CANTIDADES_PAJAROS = (5, 8, 11, 14, 18)
# Probabilidad de que cada ave dé saltitos. Nunca saltan todas y en los dos
# primeros niveles se quedan quietas.
PROBABILIDAD_SALTO = (0.0, 0.0, 0.3, 0.45, 0.55)
TIEMPO_ESPERA_RESPUESTA = 20
TIEMPO_ESPERA_ESCRITURA = 120
TIEMPO_CUENTA_PREVIA = 3.0
TIEMPO_FLASH_PALABRA = 0.8
PUNTOS_LETRA = {"primera": 30, "posterior": 20, "automatica": 10}
BONO_MAXIMO = 50
BONO_POR_SEGUNDO = 5

# Cuenta Cajas: modo propio, fuera de JUEGOS para no alterar el mejor-de-3.
RONDAS_CAJAS = 10
TIEMPO_CUENTA_CAJAS = 3.0
TIEMPO_RESPUESTA_CAJAS = 10
PUNTOS_BASE_CAJAS = 100
BONO_MAXIMO_CAJAS = 50
BONO_POR_SEGUNDO_CAJAS = 5

# Operaciones: misma mecánica que palabras, pero con cifras manuscritas.
RONDAS_OPERACIONES = 10
TIEMPO_FLASH_OPERACION = 0.9
TIEMPO_ESPERA_OPERACIONES = 60
PUNTOS_DIGITO = {"primera": 30, "posterior": 20, "automatica": 10}
BONO_MAXIMO_OPERACIONES = 50
BONO_POR_SEGUNDO_OPERACIONES = 5

# Minijuegos de entrenamiento: el puntaje Brain Age es tiempo + 2 s por error
# (menor es mejor). Para el podio se invierte a puntos altos, como el resto.
TIEMPO_CUENTA_MINI = 3.0
TIEMPO_ESPERA_MINI = 60.0
TIEMPO_RESPUESTA_MINI = {
    "stroop": 3.0,
    "triangulos": 60.0,
    "relojes": 60.0,
    "menor": 30.0,
    "memoria": 20.0,
    "vuelto": 30.0,
    "silabas": 60.0,
}
SEGUNDOS_POR_ERROR = 2.0
PUNTOS_MINI_BASE = 1000
PUNTOS_MINI_POR_SEGUNDO = 10
TIPOS_RESPUESTA_MINI = {
    **{f"{j}_answer": j for j in JUEGOS_MINI if j not in JUEGOS_ESCRITURA},
    **{f"{j}_digit": j for j in JUEGOS_ESCRITURA},
}
# Campos que el árbitro guarda pero que jamás deben viajar en el estímulo.
SECRETOS_MINI = {
    "stroop": ("correcta", "clave"),
    "triangulos": ("intermedios", "resultado", "esperado"),
    "relojes": ("horas", "minutos", "esperado", "digital1", "digital2"),
    "menor": ("orden",),
    "memoria": (),  # la pantalla necesita la grilla; solo los mandos la ocultan
    "vuelto": ("vuelto", "vuelto_texto", "optimo"),
    "silabas": ("silabas", "total", "esperado", "pista"),
}
PUERTO = 8000

reconocedor = Reconocedor()
reconocedor_digitos = ReconocedorDigitos()
app = FastAPI(title="Konitive - Laboratorio de Atención")
app.mount("/static", StaticFiles(directory=ESTATICO), name="static")
salas: dict[str, "Sala"] = {}


class SalirSala(Exception):
    """El jugador pulsó «salir» y hay que cerrar su conexión."""


@dataclass
class Jugador:
    id: str
    nombre: str
    ws: WebSocket
    rol: str = "jugador"  # "jugador", "pantalla" o "mando"
    conectado: bool = True
    cerrojo: asyncio.Lock = field(default_factory=asyncio.Lock)
    progreso: dict = field(default_factory=dict)

    async def enviar(self, mensaje: dict) -> None:
        if not self.conectado:
            return
        try:
            async with self.cerrojo:
                await self.ws.send_json(mensaje)
        except Exception:
            self.conectado = False


@dataclass
class Sala:
    codigo: str
    host_id: str
    jugadores: dict[str, Jugador] = field(default_factory=dict)
    fase: str = "lobby"
    ganadas: dict[str, dict[str, int]] = field(default_factory=dict)
    rondas_juego: dict[str, int] = field(default_factory=dict)
    usadas: set[str] = field(default_factory=set)
    anunciados: set[str] = field(default_factory=set)
    puntos: dict[str, int] = field(default_factory=dict)
    ultimo_juego: str | None = None
    desempate: bool = False
    juego_desempate: str | None = None
    practica: bool = False
    cancelada: bool = False
    evento_respuestas: asyncio.Event = field(default_factory=asyncio.Event)
    evento_escritura: asyncio.Event = field(default_factory=asyncio.Event)
    evento_cancelar: asyncio.Event = field(default_factory=asyncio.Event)
    datos: dict = field(default_factory=dict)
    modo: str = "partida"
    capacidad: int = 2
    juego_fiesta: str | None = None
    fiesta_puntos: dict[str, int] = field(default_factory=dict)
    podium_antes: list[dict] = field(default_factory=list)
    ultimos_puntos: dict[str, int] = field(default_factory=dict)
    respuestas: dict[str, tuple[int, float]] = field(default_factory=dict)
    conteos_vivos: dict[str, int] = field(default_factory=dict)
    conteos_confirmados: set[str] = field(default_factory=set)
    historial: dict[str, list[dict]] = field(default_factory=dict)
    evento_continuar: asyncio.Event = field(default_factory=asyncio.Event)
    tarea: asyncio.Task | None = None
    # Individual: secuencia de juegos elegidos y resultados acumulados.
    secuencia_individual: bool = False
    juegos_individual: list[str] = field(default_factory=list)
    juego_individual: str | None = None
    resultados_individual: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.reiniciar_marcador()

    def reiniciar_marcador(self) -> None:
        self.ganadas = {j: {} for j in JUEGOS}
        self.rondas_juego = {j: 0 for j in JUEGOS}
        self.usadas = set()
        self.anunciados = set()
        self.puntos = {}
        self.ultimo_juego = None
        self.desempate = False
        self.juego_desempate = None
        self.respuestas = {}
        self.conteos_vivos = {}
        self.conteos_confirmados = set()
        self.historial = {j: [] for j in JUEGOS}
        self.evento_continuar.clear()
        for jugador in self.jugadores.values():
            jugador.progreso = {}

    def marcador(self) -> dict:
        ids = [j.id for j in participantes(self)]
        return {
            "pajaros": {pid: self.ganadas["pajaros"].get(pid, 0) for pid in ids},
            "escritura": {pid: self.ganadas["escritura"].get(pid, 0) for pid in ids},
            "necesario": VICTORIAS_NECESARIAS,
        }

    async def difundir(self, mensaje: dict) -> None:
        for jugador in list(self.jugadores.values()):
            await jugador.enviar(mensaje)


def nuevo_codigo() -> str:
    alfabeto = string.ascii_uppercase + string.digits
    while True:
        codigo = "".join(random.choice(alfabeto) for _ in range(5))
        if codigo not in salas:
            return codigo


def ganador_de_juego(sala: Sala, juego: str) -> str | None:
    for pid, victorias in sala.ganadas[juego].items():
        if victorias >= VICTORIAS_NECESARIAS:
            return pid
    return None


def elegir_juego(sala: Sala) -> str | None:
    if sala.desempate:
        return sala.juego_desempate
    if sala.juego_fiesta:
        # En fiesta el host elige un solo juego: se juega hasta tener campeón.
        return (
            sala.juego_fiesta
            if ganador_de_juego(sala, sala.juego_fiesta) is None
            else None
        )
    activos = [j for j in JUEGOS if ganador_de_juego(sala, j) is None]
    if sala.secuencia_individual and sala.juego_individual in JUEGOS:
        # En la secuencia individual solo se juega el juego actual, hasta
        # completar sus 3 victorias; luego el orquestador pasa al siguiente.
        activos = (
            [sala.juego_individual]
            if ganador_de_juego(sala, sala.juego_individual) is None
            else []
        )
    if not activos:
        return None
    if sala.ultimo_juego in activos and len(activos) > 1:
        return next(j for j in JUEGOS if j in activos and j != sala.ultimo_juego)
    return activos[0]


def decidir_ganador(puntos: dict[str, int]) -> str | None:
    if not puntos:
        return None
    maximo = max(puntos.values())
    empatados = [pid for pid, valor in puntos.items() if valor == maximo]
    return empatados[0] if len(empatados) == 1 else None


async def esperar(sala: Sala, evento: asyncio.Event, segundos: float | None) -> None:
    """Espera un evento, un timeout (o ninguno) o la cancelación de la partida."""
    t_evento = asyncio.create_task(evento.wait())
    t_cancel = asyncio.create_task(sala.evento_cancelar.wait())
    try:
        listo, pendientes = await asyncio.wait(
            {t_evento, t_cancel},
            timeout=segundos,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if t_cancel in listo:
            sala.cancelada = True
        for tarea in pendientes:
            tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarea
    finally:
        for tarea in (t_evento, t_cancel):
            if not tarea.done():
                tarea.cancel()


async def pausa(sala: Sala, segundos: float) -> None:
    await esperar(sala, asyncio.Event(), segundos)


def participantes(sala: Sala) -> list[Jugador]:
    """Quienes juegan: en fiesta solo los mandos (la pantalla no puntúa)."""
    if sala.modo == "fiesta":
        return [j for j in sala.jugadores.values() if j.rol == "mando"]
    return list(sala.jugadores.values())


async def difundir_roles(
    sala: Sala, completo: dict, para_mandos: dict | None = None
) -> None:
    """En fiesta los mandos reciben una versión sin datos que deban memorizar."""
    for jugador in sala.jugadores.values():
        mensaje = completo
        if (
            sala.modo == "fiesta"
            and jugador.rol == "mando"
            and para_mandos is not None
        ):
            mensaje = para_mandos
        await jugador.enviar(mensaje)


def ip_local() -> str:
    """IP de la red local para que el celular pueda escanear el QR."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def clasificacion(sala: Sala) -> list[dict]:
    filas = [
        {"id": j.id, "nombre": j.nombre, "puntos": sala.fiesta_puntos.get(j.id, 0)}
        for j in participantes(sala)
    ]
    return sorted(filas, key=lambda fila: (-fila["puntos"], fila["nombre"].casefold()))


async def emitir_podium(sala: Sala, final: bool = False) -> None:
    """Muestra el podio animado y devuelve al host al selector de juegos."""
    for pid, puntos in sala.ultimos_puntos.items():
        sala.fiesta_puntos[pid] = sala.fiesta_puntos.get(pid, 0) + puntos
    filas = clasificacion(sala)
    antes = sala.podium_antes
    await sala.difundir(
        {
            "type": "podium_final" if final else "podium_update",
            "antes": antes,
            "despues": filas,
            "puntos_juego": dict(sala.ultimos_puntos),
            "juego": sala.juego_fiesta,
            "nombre_juego": NOMBRES_JUEGOS.get(sala.juego_fiesta or "", ""),
        }
    )
    if final:
        sala.fase = "fin"
        return
    await pausa(sala, TIEMPO_PODIO)
    sala.fase = "lobby"
    sala.juego_fiesta = None
    sala.ultimos_puntos = {}
    sala.tarea = None
    await sala.difundir(
        {
            "type": "back_to_selector",
            "podio": clasificacion(sala),
            "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
            "host": sala.host_id,
        }
    )


def generar_pajaros(nivel: int) -> list[dict]:
    """Aves quietas o con saltitos cortos y desplazamiento mínimo."""
    cantidad = CANTIDADES_PAJAROS[min(nivel - 1, len(CANTIDADES_PAJAROS) - 1)]
    probabilidad = PROBABILIDAD_SALTO[min(nivel - 1, len(PROBABILIDAD_SALTO) - 1)]
    aves: list[dict] = []
    for i in range(cantidad):
        for _ in range(40):
            x, y = random.uniform(0.08, 0.92), random.uniform(0.14, 0.86)
            if all((x - a["x"]) ** 2 + (y - a["y"]) ** 2 > 0.008 for a in aves):
                break
        salta = random.random() < probabilidad
        aves.append(
            {
                "id": i,
                "x": round(x, 4),
                "y": round(y, 4),
                "size": random.randint(26, 44),
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


async def difundir_conteos(sala: Sala) -> None:
    await sala.difundir({"type": "bird_tally", **estado_conteos(sala)})


async def ronda_pajaros(sala: Sala, nivel: int) -> dict[str, int]:
    aves = generar_pajaros(nivel)
    duracion = 3.6 if nivel <= 2 else 3.2
    sala.datos.update({"esperado": len(aves), "aves": aves})
    sala.respuestas = {}
    sala.conteos_vivos = {j.id: 0 for j in participantes(sala)}
    sala.conteos_confirmados = set()
    sala.evento_respuestas.clear()

    sala.datos["momento_respuesta"] = time.monotonic()
    sala.datos["conteo_token"] = uuid.uuid4().hex
    token = sala.datos["conteo_token"]
    await difundir_roles(
        sala,
        {
            "type": "birds_show",
            "aves": aves,
            "duracion": duracion,
            "nivel": nivel,
            "marcador": sala.marcador(),
            "token": token,
        },
        # Los mandos de la fiesta miran la pantalla: no reciben las aves.
        {"type": "birds_show", "duracion": duracion, "nivel": nivel, "token": token},
    )
    # Las aves se ven durante toda la fase de observación; el cliente las deja
    # en pantalla mientras se cuenta, y el éxito se mide por el tiempo.
    await pausa(sala, duracion)
    await sala.difundir(
        {
            "type": "birds_hide",
            "segundos": TIEMPO_ESPERA_RESPUESTA,
            **estado_conteos(sala),
            "token": token,
        }
    )
    await esperar(sala, sala.evento_respuestas, TIEMPO_ESPERA_RESPUESTA)

    # Si alguien no confirmó a tiempo, se usa el último número que tenía en
    # pantalla, pero sin bonus de rapidez.
    momento = sala.datos["momento_respuesta"]
    for pid, conteo in sala.conteos_vivos.items():
        if pid not in sala.respuestas:
            sala.respuestas[pid] = (conteo, momento + TIEMPO_ESPERA_RESPUESTA + 1)

    puntos: dict[str, int] = {}
    for jugador in participantes(sala):
        pid = jugador.id
        respuesta = sala.respuestas.get(pid)
        if respuesta is None:
            puntos[pid] = 0
            continue
        conteo, instante = respuesta
        if conteo != sala.datos["esperado"]:
            puntos[pid] = 0
            continue
        tardanza = instante - sala.datos["momento_respuesta"]
        puntos[pid] = 100 + max(0, 100 - int(tardanza * 20))
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

    await sala.difundir(
        {
            "type": "word_countdown",
            "segundos": TIEMPO_CUENTA_PREVIA,
            "nivel": nivel,
            "marcador": sala.marcador(),
        }
    )
    await pausa(sala, TIEMPO_CUENTA_PREVIA)
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
    await pausa(sala, TIEMPO_FLASH_PALABRA)
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
    for jugador in participantes(sala):
        progreso = jugador.progreso
        if not progreso or progreso.get("inicio") is None:
            puntos[jugador.id] = 0
            desglose[jugador.id] = {
                "letras": 0,
                "bono": 0,
                "total": 0,
                "correctas": 0,
                "automaticas": 0,
            }
            continue

        base = sum(letra["puntos"] for letra in progreso["letras"])
        correctas = sum(
            1 for letra in progreso["letras"] if letra["motivo"] != "automatica"
        )
        automaticas = sum(
            1 for letra in progreso["letras"] if letra["motivo"] == "automatica"
        )
        bono = 0
        if progreso["fin"] is not None:
            tardanza = max(0.0, progreso["fin"] - progreso["inicio"])
            bono = max(0, BONO_MAXIMO - int(tardanza * BONO_POR_SEGUNDO))

        total = base + bono
        puntos[jugador.id] = total
        desglose[jugador.id] = {
            "letras": base,
            "bono": bono,
            "total": total,
            "correctas": correctas,
            "automaticas": automaticas,
        }

    sala.datos["desglose"] = desglose
    return puntos


def registrar_resultado_individual(sala: Sala, juego: str, datos: dict) -> None:
    """Guarda el resultado de un juego de la secuencia individual."""
    sala.resultados_individual[juego] = datos


def resumen_clasico_individual(sala: Sala, juego: str) -> dict:
    """Resultado de PÁJAROS o PALABRAS dentro de la secuencia individual."""
    pid = next(iter(sala.jugadores), sala.host_id)
    puntos = [entrada["puntos"].get(pid, 0) for entrada in sala.historial[juego]]
    return {
        "rondas": sala.rondas_juego[juego],
        "victorias": sala.ganadas[juego].get(pid, 0),
        "mejor": max(puntos, default=0),
        "total": sum(puntos),
        "puntos": sum(puntos),
    }


async def enviar_resumen_practica(sala: Sala) -> None:
    """Entrega un informe de la tanda de práctica y espera a seguir o salir."""
    pid = next(iter(sala.jugadores), sala.host_id)
    resumen: dict[str, dict] = {}
    for juego in JUEGOS:
        puntos = [
            entrada["puntos"].get(pid, 0) for entrada in sala.historial[juego]
        ]
        resumen[juego] = {
            "rondas": sala.rondas_juego[juego],
            "victorias": sala.ganadas[juego].get(pid, 0),
            "mejor": max(puntos, default=0),
            "total": sum(puntos),
        }

    sala.fase = "resumen"
    sala.evento_continuar.clear()
    await sala.difundir(
        {
            "type": "practice_summary",
            "resumen": resumen,
            "marcador": sala.marcador(),
            "nombre": sala.jugadores[pid].nombre,
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
        "necesario": RONDAS_CAJAS,
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

    try:
        await pausa(sala, 0.6)
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

        for ronda in range(1, RONDAS_CAJAS + 1):
            if sala.cancelada:
                return
            racha_referencia = max(rachas.values(), default=0)
            indice_dificultad = min(len(DIFICULTADES) - 1, racha_referencia // 3)
            pila = generar_pila(indice_dificultad, anterior)
            anterior = pila["alturas"]
            multiplicador = 1 + indice_dificultad

            sala.datos = {
                "juego": "cajas",
                "nivel": indice_dificultad + 1,
                "pila": pila,
                "momento_respuesta": None,
            }
            sala.respuestas = {}
            sala.evento_respuestas.clear()

            await sala.difundir(
                {
                    "type": "cajas_countdown",
                    "segundos": TIEMPO_CUENTA_CAJAS,
                    "ronda": ronda,
                    "necesario": RONDAS_CAJAS,
                    "dificultad": pila["dificultad"],
                    "marcador": marcador_cajas(
                        sala, puntos, aciertos, rachas, ronda
                    ),
                }
            )
            await pausa(sala, TIEMPO_CUENTA_CAJAS)
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
            await pausa(sala, pila["segundos"])
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
            await sala.difundir(
                {
                    "type": "cajas_result",
                    "alturas": pila["alturas"],
                    "base": pila["base"],
                    "total": pila["total"],
                    "visibles": pila["visibles"],
                    "multiplicador": multiplicador,
                    "ronda": ronda,
                    "necesario": RONDAS_CAJAS,
                    "dificultad": pila["dificultad"],
                    "jugadores": por_jugador,
                    "clasificacion": clasificacion(sala),
                    "marcador": marcador_cajas(
                        sala, puntos, aciertos, rachas, ronda
                    ),
                    **principal,
                }
            )
            await pausa(sala, 3.0 if ronda < RONDAS_CAJAS else 1.0)

        if sala.secuencia_individual:
            registrar_resultado_individual(
                sala,
                "cajas",
                {
                    "rondas": RONDAS_CAJAS,
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
                "rondas": RONDAS_CAJAS,
                "nombre": sala.jugadores[primero].nombre
                if primero in sala.jugadores
                else "JUGADOR",
                "clasificacion": [
                    {
                        "id": pid,
                        "nombre": sala.jugadores[pid].nombre,
                        "puntos": puntos[pid],
                        "aciertos": aciertos[pid],
                    }
                    for pid in ids
                ],
            }
        )
    except asyncio.CancelledError:
        raise


async def bucle_partida(sala: Sala) -> None:
    try:
        await pausa(sala, 0.6)
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

            if juego == "pajaros":
                puntos = await ronda_pajaros(sala, nivel)
            else:
                puntos = await ronda_escritura(sala, nivel)
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
                    "esperado": sala.datos.get("esperado"),
                    "palabra": sala.datos.get("palabra"),
                    "ganador": ganador,
                }
            )

            await sala.difundir(
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
                }
            )
            await pausa(sala, 4.0 if not sala.practica else 2.0)
            if sala.cancelada:
                return

            if sala.practica:
                # Se alternan minijuegos hasta completar la tanda; entonces se
                # muestra el resumen y se ofrece seguir entrenando.
                continue

            if sala.juego_fiesta:
                campeon = ganador_de_juego(sala, sala.juego_fiesta)
                sala.ultimos_puntos = {
                    j.id: sum(
                        entrada["puntos"].get(j.id, 0)
                        for entrada in sala.historial[sala.juego_fiesta]
                    )
                    for j in participantes(sala)
                }
                await terminar_partida(sala, campeon)
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
                            "nombre": sala.jugadores[campeon].nombre,
                            "marcador": sala.marcador(),
                        }
                    )
                    await pausa(sala, 3.0)
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
                await pausa(sala, 3.5)
    except asyncio.CancelledError:
        pass


def trazos_validos(mensaje: dict) -> list[list[tuple[float, float]]]:
    """Normaliza y valida los trazos que llegan desde el canvas."""
    trazos = mensaje.get("trazos")
    if not isinstance(trazos, list) or len(trazos) > 20:
        return []
    limpios: list[list[tuple[float, float]]] = []
    for trazo in trazos:
        if not isinstance(trazo, list) or len(trazo) > 400:
            continue
        puntos: list[tuple[float, float]] = []
        for par in trazo:
            if isinstance(par, (list, tuple)) and len(par) == 2:
                x, y = par
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    puntos.append(
                        (min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y))))
                    )
        if puntos:
            limpios.append(puntos)
    return limpios


async def procesar_letra(sala: Sala, jugador: Jugador, mensaje: dict) -> None:
    progreso = jugador.progreso
    indice = mensaje.get("index")
    if (
        not progreso
        or sala.fase not in ("escritura", "desempate")
        or not sala.datos.get("escribiendo")
        or not isinstance(indice, int)
        or not 0 <= indice < len(progreso["palabra"])
        or (sala.modo == "fiesta" and jugador.rol != "mando")
    ):
        return

    estado = progreso["letras"][indice]
    if estado["estado"] == "aceptada":
        return

    limpios = trazos_validos(mensaje)
    if not limpios:
        return

    esperada = progreso["palabra"][indice]
    predicha, confianza, _ = reconocedor.reconocer(limpios)
    estado["intentos"] += 1

    if predicha == esperada:
        puntos_letra = (
            PUNTOS_LETRA["primera"] if estado["intentos"] == 1 else PUNTOS_LETRA["posterior"]
        )
        estado["estado"] = "aceptada"
        motivo = "correcta"
        tipo_punto = "primera" if estado["intentos"] == 1 else "posterior"
    elif estado["intentos"] >= 3:
        puntos_letra = PUNTOS_LETRA["automatica"]
        estado["estado"] = "aceptada"
        motivo = "aceptada por intentos"
        tipo_punto = "automatica"
    else:
        puntos_letra = 0
        motivo = "inténtalo otra vez"
        tipo_punto = ""
    estado["puntos"] = puntos_letra
    estado["motivo"] = tipo_punto

    await jugador.enviar(
        {
            "type": "letter_feedback",
            "index": indice,
            "esperada": esperada,
            "predicha": predicha,
            "confianza": round(confianza, 2),
            "intentos": estado["intentos"],
            "aceptada": estado["estado"] == "aceptada",
            "puntos": puntos_letra,
            "motivo": motivo,
        }
    )

    if all(letra["estado"] == "aceptada" for letra in progreso["letras"]):
        progreso["fin"] = time.monotonic()
        await jugador.enviar(
            {
                "type": "word_done",
                "puntos": sum(l["puntos"] for l in progreso["letras"]),
                "automaticas": sum(
                    1 for l in progreso["letras"] if l["motivo"] == "automatica"
                ),
            }
        )
        if all(j.progreso.get("fin") is not None for j in participantes(sala)):
            sala.evento_escritura.set()


async def procesar_digito(sala: Sala, jugador: Jugador, mensaje: dict) -> None:
    """Reconoce una cifra manuscrita, igual que una letra pero con 10 clases."""
    progreso = jugador.progreso
    indice = mensaje.get("index")
    if (
        not progreso
        or sala.fase not in ("operaciones", "desempate")
        or not sala.datos.get("escribiendo")
        or not isinstance(indice, int)
        or not 0 <= indice < len(progreso["digitos"])
        or (sala.modo == "fiesta" and jugador.rol != "mando")
    ):
        return

    estado = progreso["digitos"][indice]
    if estado["estado"] == "aceptada":
        return

    limpios = trazos_validos(mensaje)
    if not limpios:
        return

    esperada = progreso["resultado"][indice]
    predicha, confianza, _ = reconocedor_digitos.reconocer(limpios)
    estado["intentos"] += 1

    if predicha == esperada:
        puntos_digito = (
            PUNTOS_DIGITO["primera"]
            if estado["intentos"] == 1
            else PUNTOS_DIGITO["posterior"]
        )
        estado["estado"] = "aceptada"
        motivo = "correcta"
        tipo_punto = "primera" if estado["intentos"] == 1 else "posterior"
    elif estado["intentos"] >= 3:
        puntos_digito = PUNTOS_DIGITO["automatica"]
        estado["estado"] = "aceptada"
        motivo = "aceptada por intentos"
        tipo_punto = "automatica"
    else:
        puntos_digito = 0
        motivo = "inténtalo otra vez"
        tipo_punto = ""
    estado["puntos"] = puntos_digito
    estado["motivo"] = tipo_punto

    await jugador.enviar(
        {
            "type": "digit_feedback",
            "index": indice,
            "esperada": esperada,
            "predicha": predicha,
            "confianza": round(confianza, 2),
            "intentos": estado["intentos"],
            "aceptada": estado["estado"] == "aceptada",
            "puntos": puntos_digito,
            "motivo": motivo,
        }
    )

    if all(d["estado"] == "aceptada" for d in progreso["digitos"]):
        progreso["fin"] = time.monotonic()
        await jugador.enviar(
            {
                "type": "operacion_done",
                "puntos": sum(d["puntos"] for d in progreso["digitos"]),
                "automaticas": sum(
                    1 for d in progreso["digitos"] if d["motivo"] == "automatica"
                ),
            }
        )
        if all(j.progreso.get("fin") is not None for j in participantes(sala)):
            sala.evento_escritura.set()


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
        "necesario": RONDAS_OPERACIONES,
    }


async def bucle_operaciones(sala: Sala) -> None:
    """Diez operaciones; en fiesta todos los mandos escriben a la vez."""
    jugadores_ = participantes(sala)
    ids = [j.id for j in jugadores_]
    puntos = {pid: 0 for pid in ids}
    anterior: str | None = None
    sala.ultimos_puntos = {}

    try:
        await pausa(sala, 0.6)
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

        for ronda in range(1, RONDAS_OPERACIONES + 1):
            if sala.cancelada:
                return
            operacion = generar_operacion(ronda, anterior)
            anterior = operacion["texto"]
            sala.datos = {
                "juego": "operaciones",
                "nivel": operacion["nivel"],
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

            await sala.difundir(
                {
                    "type": "operacion_countdown",
                    "segundos": TIEMPO_CUENTA_PREVIA,
                    "ronda": ronda,
                    "necesario": RONDAS_OPERACIONES,
                    "dificultad": operacion["dificultad"],
                    "marcador": marcador_operaciones(sala, puntos, ronda),
                }
            )
            await pausa(sala, TIEMPO_CUENTA_PREVIA)
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
            await pausa(sala, TIEMPO_FLASH_OPERACION)
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
                base = sum(d["puntos"] for d in progreso["digitos"])
                automaticas = sum(
                    1 for d in progreso["digitos"] if d["motivo"] == "automatica"
                )
                correctas = sum(
                    1 for d in progreso["digitos"] if d["motivo"] != "automatica"
                )
                bono = 0
                if progreso["fin"] is not None:
                    tardanza = max(0.0, progreso["fin"] - inicio)
                    bono = max(
                        0,
                        BONO_MAXIMO_OPERACIONES
                        - int(tardanza * BONO_POR_SEGUNDO_OPERACIONES),
                    )
                total = base + bono
                puntos[jugador.id] += total
                desglose[jugador.id] = {
                    "digitos": base,
                    "bono": bono,
                    "total": total,
                    "correctas": correctas,
                    "automaticas": automaticas,
                }

            await sala.difundir(
                {
                    "type": "operacion_result",
                    "texto": operacion["texto"],
                    "resultado": operacion["resultado"],
                    "ronda": ronda,
                    "necesario": RONDAS_OPERACIONES,
                    "dificultad": operacion["dificultad"],
                    "desglose": desglose,
                    "clasificacion": clasificacion(sala),
                    "marcador": marcador_operaciones(sala, puntos, ronda),
                }
            )
            await pausa(sala, 3.0 if ronda < RONDAS_OPERACIONES else 1.0)

        if sala.secuencia_individual:
            registrar_resultado_individual(
                sala,
                "operaciones",
                {
                    "rondas": RONDAS_OPERACIONES,
                    "puntos": puntos.get(ids[0], 0) if ids else 0,
                },
            )
            return

        sala.fase = "fin"
        sala.ultimos_puntos = dict(puntos)
        primero = ids[0] if ids else sala.host_id
        await sala.difundir(
            {
                "type": "operacion_over",
                "puntos": puntos.get(primero, 0),
                "rondas": RONDAS_OPERACIONES,
                "nombre": sala.jugadores[primero].nombre
                if primero in sala.jugadores
                else "JUGADOR",
                "clasificacion": [
                    {"id": pid, "nombre": sala.jugadores[pid].nombre, "puntos": puntos[pid]}
                    for pid in ids
                ],
            }
        )
    except asyncio.CancelledError:
        raise


# ---------------------------------------------------------------------------
# Minijuegos de entrenamiento (Stroop, Triángulos, Relojes, Menor a mayor,
# Memoria, Vuelto y Sílabas). Todos comparten este bucle: la fase lleva el
# nombre del juego, las respuestas incluyen ronda y jugador, y el host mide
# los tiempos y calcula el puntaje Brain Age.
# ---------------------------------------------------------------------------
def marcador_mini(sala: Sala, juego: str, puntos: dict[str, int], ronda: int) -> dict:
    ids = [j.id for j in participantes(sala)]
    primero = ids[0] if ids else sala.host_id
    return {
        juego: {
            pid: {"puntos": puntos.get(pid, 0), "ronda": ronda} for pid in ids
        },
        "nombre": sala.jugadores[primero].nombre
        if primero in sala.jugadores
        else "JUGADOR",
        "necesario": RONDAS_MINI[juego],
    }


def brain_age_y_puntos(tiempo: float, errores: int) -> tuple[float, int]:
    """Brain Age: tiempo + 2 s por error, menor es mejor. Se invierte para el podio."""
    brain = tiempo + SEGUNDOS_POR_ERROR * errores
    puntos = max(0, round(PUNTOS_MINI_BASE - brain * PUNTOS_MINI_POR_SEGUNDO))
    return brain, puntos


def datos_para_resultado(juego: str, reto: dict) -> dict:
    """Solo los campos que deben revelarse al terminar la ronda."""
    claves = {
        "stroop": ("palabra", "tinta", "correcta"),
        "triangulos": ("top", "ops", "op_final", "intermedios", "resultado"),
        "relojes": ("reloj1", "reloj2", "digital1", "digital2", "horas", "minutos"),
        "menor": ("numeros", "orden"),
        "memoria": ("grilla", "posiciones", "cantidad"),
        "vuelto": ("producto", "precio_texto", "pago_texto", "vuelto_texto", "optimo"),
        "silabas": ("frase", "silabas", "pista", "total"),
    }[juego]
    return {clave: reto[clave] for clave in claves}


def estimulo_para_mando(juego: str, reto: dict) -> dict:
    """Lo que el celular puede mostrar sin revelar la respuesta correcta.

    Memoria es la excepción: su grilla es privada y el mando solo mira la
    pantalla mientras la memoriza.
    """
    claves = {
        "stroop": ("palabra", "tinta"),
        "triangulos": ("top", "ops", "op_final"),
        "relojes": ("reloj1", "reloj2"),
        "menor": ("numeros",),
        "memoria": (),
        "vuelto": ("producto", "precio_texto", "pago_texto"),
        "silabas": ("frase",),
    }[juego]
    datos = {clave: reto[clave] for clave in claves}
    if juego == "memoria":
        datos["mira"] = True
    return datos


async def _feedback_privado(
    sala: Sala, jugador: Jugador, juego: str, acepta: bool, **extra
) -> None:
    """Feedback verde/rojo solo al jugador que respondió."""
    await jugador.enviar(
        {
            "type": f"{juego}_feedback",
            "pid": jugador.id,
            "acepta": acepta,
            "aceptada": acepta,
            **extra,
        }
    )
    await sala.difundir(
        {
            "type": "mini_progreso",
            "juego": juego,
            "pid": jugador.id,
            "acepta": acepta,
            "marcados": len(jugador.progreso.get("secuencia", [])),
            "total": len(jugador.progreso.get("esperado", ""))
            or jugador.progreso.get("total", 0),
            "fallos": jugador.progreso.get("fallos", 0),
        }
    )


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
        if casilla["estado"] == "aceptada":
            return
        trazos = trazos_validos(mensaje)
        if not trazos:
            return
        try:
            predicha, _confianza, _ = reconocedor_digitos.reconocer(trazos)
        except Exception:
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
        if respuesta in secuencia:
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
            total = sum(
                int(clave) * cantidad
                for clave, cantidad in respuesta.items()
                if str(clave).isdigit() and isinstance(cantidad, int)
            )
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
    puntos = {pid: PUNTOS_MINI_BASE for pid in ids}
    anterior = None
    sala.ultimos_puntos = {}
    total_rondas = RONDAS_MINI[juego]
    espera = TIEMPO_RESPUESTA_MINI[juego]

    try:
        await pausa(sala, 0.6)
        if sala.cancelada:
            return
        sala.fase = juego
        await sala.difundir(
            {
                "type": "match_start",
                "modo": juego,
                "marcador": marcador_mini(sala, juego, puntos, 0),
            }
        )

        for ronda in range(1, total_rondas + 1):
            if sala.cancelada:
                return
            reto = generar(ronda, juego, anterior)
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

            await sala.difundir(
                {
                    "type": f"{juego}_countdown",
                    "segundos": TIEMPO_CUENTA_MINI,
                    "ronda": ronda,
                    "necesario": total_rondas,
                    "dificultad": reto.get("dificultad", ""),
                    "marcador": marcador_mini(sala, juego, puntos, ronda),
                }
            )
            await pausa(sala, TIEMPO_CUENTA_MINI)
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
            if juego == "memoria":
                completo["duracion"] = reto["segundos"]
                para_mandos["duracion"] = reto["segundos"]
            await difundir_roles(sala, completo, para_mandos)

            if juego == "memoria":
                await pausa(sala, reto["segundos"])
                if sala.cancelada:
                    return
                sala.datos["momento_respuesta"] = time.monotonic()
                await sala.difundir(
                    {"type": "memoria_hide", "ronda": ronda, "grilla": reto["grilla"]}
                )
            else:
                sala.datos["momento_respuesta"] = time.monotonic()

            datos_write: dict = {}
            if juego == "menor":
                datos_write = {"numeros": reto["numeros"]}
            elif juego == "memoria":
                datos_write = {
                    "grilla": reto["grilla"],
                    "celdas": reto["celdas"],
                    "cantidad": reto["cantidad"],
                }
            elif juego == "vuelto":
                datos_write = {
                    "denominaciones": reto["denominaciones"],
                    "producto": reto["producto"],
                    "precio_texto": reto["precio_texto"],
                    "pago_texto": reto["pago_texto"],
                }
            elif juego in JUEGOS_ESCRITURA:
                datos_write = {
                    "digitos": len(reto["esperado"]),
                    "campo": {
                        "triangulos": "RESULTADO FINAL",
                        "relojes": "HORAS Y MINUTOS",
                        "silabas": "NÚMERO DE SÍLABAS",
                    }[juego],
                    "estimulo": estimulo_para_mando(juego, reto),
                }
            await sala.difundir(
                {
                    "type": f"{juego}_write",
                    "ronda": ronda,
                    "marcador": marcador_mini(sala, juego, puntos, ronda),
                    **datos_write,
                }
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
                    errores = progreso["fallos"]
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
                    else:
                        acierto = bool(respuesta) and progreso.get("total_entregado") == reto["vuelto"]
                    errores = progreso["fallos"]
                    fin = progreso["fin"] or ahora
                if not respuesta and juego not in JUEGOS_ESCRITURA:
                    tiempo = espera
                else:
                    tiempo = max(0.0, fin - momento)
                if acierto:
                    aciertos[pid] += 1
                fallos[pid] += errores
                tiempos[pid] += tiempo
                brain, puntos[pid] = brain_age_y_puntos(tiempos[pid], fallos[pid])
                por_jugador[pid] = {
                    "acierto": acierto,
                    "errores": errores,
                    "tiempo": round(tiempo, 2),
                    "brain_age": round(brain, 2),
                    "puntos": puntos[pid],
                }

            principal = por_jugador[ids[0]] if ids else {}
            await sala.difundir(
                {
                    "type": f"{juego}_result",
                    "ronda": ronda,
                    "necesario": total_rondas,
                    "dificultad": reto.get("dificultad", ""),
                    "reto": datos_para_resultado(juego, reto),
                    "jugadores": por_jugador,
                    "clasificacion": clasificacion(sala),
                    "marcador": marcador_mini(sala, juego, puntos, ronda),
                    **principal,
                }
            )
            await pausa(sala, 2.5 if ronda < total_rondas else 1.0)

        pid = ids[0] if ids else sala.host_id
        brain, _ = brain_age_y_puntos(tiempos.get(pid, 0.0), fallos.get(pid, 0))
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
            "puntos": puntos.get(pid, 0),
        }

        if sala.secuencia_individual:
            registrar_resultado_individual(sala, juego, resumen)
            return

        sala.fase = "fin"
        sala.ultimos_puntos = dict(puntos)
        await sala.difundir(
            {
                "type": f"{juego}_over",
                "nombre": sala.jugadores[pid].nombre if pid in sala.jugadores else "JUGADOR",
                "clasificacion": [
                    {
                        "id": jugador.id,
                        "nombre": jugador.nombre,
                        "puntos": puntos[jugador.id],
                        "brain_age": round(
                            brain_age_y_puntos(
                                tiempos[jugador.id], fallos[jugador.id]
                            )[0],
                            2,
                        ),
                    }
                    for jugador in jugadores_
                ],
                **resumen,
            }
        )
    except asyncio.CancelledError:
        raise


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
            await pausa(sala, 1.2)
            if sala.cancelada:
                return

            sala.reiniciar_marcador()
            sala.fase = "jugando"
            if juego in JUEGOS:
                await bucle_partida(sala)
            elif juego == "cajas":
                await bucle_cajas(sala)
            elif juego == "operaciones":
                await bucle_operaciones(sala)
            elif juego in JUEGOS_MINI:
                await bucle_minijuego(sala, juego)
            if sala.cancelada:
                return

        sala.fase = "fin"
        await sala.difundir(
            {
                "type": "individual_summary",
                "nombre": nombre,
                "resumen": sala.resultados_individual,
                "orden": sala.juegos_individual,
                "total": sum(dato.get("puntos", 0) for dato in sala.resultados_individual.values()),
            }
        )
    except asyncio.CancelledError:
        pass


async def bucle_fiesta(sala: Sala, juego: str) -> None:
    """Ejecuta el juego elegido por el host y muestra el podio después."""
    try:
        if juego in ("pajaros", "escritura"):
            await bucle_partida(sala)
        elif juego == "cajas":
            await bucle_cajas(sala)
        elif juego == "operaciones":
            await bucle_operaciones(sala)
        elif juego in JUEGOS_MINI:
            await bucle_minijuego(sala, juego)
    except asyncio.CancelledError:
        raise
    if not sala.cancelada:
        await emitir_podium(sala)


async def manejar_mensaje(sala: Sala, jugador: Jugador, mensaje: dict) -> None:
    tipo = mensaje.get("type")

    if tipo == "start":
        if (
            jugador.id != sala.host_id
            or sala.fase != "lobby"
            or sala.tarea is not None
        ):
            return
        juego = mensaje.get("juego")
        if sala.modo == "fiesta":
            if juego not in JUEGOS_FIESTA or not participantes(sala):
                return
            sala.juego_fiesta = juego
            sala.podium_antes = clasificacion(sala)
        elif len(sala.jugadores) < 2:
            return
        sala.reiniciar_marcador()
        sala.cancelada = False
        sala.evento_cancelar.clear()
        sala.fase = "jugando"
        if sala.modo == "fiesta":
            sala.tarea = asyncio.create_task(bucle_fiesta(sala, juego))
        else:
            sala.tarea = asyncio.create_task(bucle_partida(sala))

    elif tipo == "finish_fiesta":
        if (
            sala.modo == "fiesta"
            and jugador.id == sala.host_id
            and sala.fase == "lobby"
            and sala.tarea is None
        ):
            await emitir_podium(sala, final=True)

    elif tipo == "restart":
        if sala.fase == "fin" and jugador.id == sala.host_id:
            sala.tarea = None
            sala.fase = "lobby"
            await sala.difundir({"type":"back_to_lobby","marcador":sala.marcador()})

    elif tipo == "bird_tally" and sala.fase in ("pajaros", "desempate"):
        if sala.modo == "fiesta" and jugador.rol != "mando":
            return
        conteo = mensaje.get("count")
        token = mensaje.get("token")
        if (
            isinstance(conteo, int)
            and 0 <= conteo <= 200
            and "momento_respuesta" in sala.datos
            and (token is None or token == sala.datos.get("conteo_token"))
            and jugador.id not in sala.conteos_confirmados
        ):
            sala.conteos_vivos[jugador.id] = conteo
            await difundir_conteos(sala)

    elif tipo == "bird_answer" and sala.fase in ("pajaros", "desempate"):
        if sala.modo == "fiesta" and jugador.rol != "mando":
            return
        conteo = mensaje.get("count")
        token = mensaje.get("token")
        if (
            isinstance(conteo, int)
            and 0 <= conteo <= 200
            and "momento_respuesta" in sala.datos
            and (token is None or token == sala.datos.get("conteo_token"))
            and jugador.id not in sala.respuestas
        ):
            sala.conteos_vivos[jugador.id] = conteo
            sala.conteos_confirmados.add(jugador.id)
            sala.respuestas[jugador.id] = (conteo, time.monotonic())
            await difundir_conteos(sala)
            if len(sala.respuestas) >= len(participantes(sala)):
                sala.evento_respuestas.set()

    elif tipo == "cajas_answer" and sala.fase == "cajas":
        if sala.modo not in ("cajas", "fiesta", "individual"):
            return
        if sala.modo == "fiesta" and jugador.rol != "mando":
            return
        conteo = mensaje.get("count")
        if (
            isinstance(conteo, int)
            and 0 <= conteo <= 200
            and sala.datos.get("momento_respuesta") is not None
            and jugador.id not in sala.respuestas
        ):
            sala.respuestas[jugador.id] = (conteo, time.monotonic())
            if len(sala.respuestas) >= len(participantes(sala)):
                sala.evento_respuestas.set()

    elif tipo == "cajas_restart":
        if sala.modo == "cajas" and sala.fase == "fin" and jugador.id == sala.host_id:
            sala.tarea = None
            sala.cancelada = False
            sala.evento_cancelar.clear()
            sala.fase = "jugando"
            sala.tarea = asyncio.create_task(bucle_cajas(sala))

    elif tipo in TIPOS_RESPUESTA_MINI:
        await manejar_respuesta_mini(sala, jugador, mensaje, TIPOS_RESPUESTA_MINI[tipo])

    elif tipo == "letter":
        await procesar_letra(sala, jugador, mensaje)

    elif tipo == "digit":
        await procesar_digito(sala, jugador, mensaje)

    elif tipo == "operaciones_restart":
        if (
            sala.modo == "operaciones"
            and sala.fase == "fin"
            and jugador.id == sala.host_id
        ):
            sala.tarea = None
            sala.cancelada = False
            sala.evento_cancelar.clear()
            sala.fase = "jugando"
            sala.tarea = asyncio.create_task(bucle_operaciones(sala))

    elif tipo == "individual_restart":
        if (
            sala.modo == "individual"
            and sala.fase == "fin"
            and jugador.id == sala.host_id
        ):
            sala.tarea = None
            sala.resultados_individual = {}
            sala.cancelada = False
            sala.evento_cancelar.clear()
            sala.fase = "jugando"
            sala.tarea = asyncio.create_task(bucle_individual(sala))

    elif tipo == "continue_practice":
        if sala.practica and sala.fase == "resumen":
            sala.fase = "jugando"
            sala.evento_continuar.set()

    elif tipo == "leave":
        raise SalirSala()


@app.get("/")
async def indice() -> FileResponse:
    return FileResponse(ESTATICO / "index.html")


@app.get("/api/health")
async def salud() -> dict:
    return {
        "ok": True,
        "salas": len(salas),
        "modelo": "emnist_model.onnx",
        "digitos": "mnist_model.onnx",
    }


@app.get("/api/red")
async def datos_red() -> dict:
    return {"ip": ip_local(), "puerto": PUERTO}


@app.get("/api/qr")
async def codigo_qr(texto: str = "") -> Response:
    if not texto or len(texto) > 500:
        return Response(status_code=400)
    imagen = qrcode.make(
        texto, image_factory=SvgPathImage, box_size=6, border=2
    )
    buffer = io.BytesIO()
    imagen.save(buffer)
    return Response(buffer.getvalue(), media_type="image/svg+xml")


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    await ws.accept()
    sala: Sala | None = None
    jugador: Jugador | None = None

    try:
        mensaje = await ws.receive_json()
        tipo = mensaje.get("type")
        nombre = str(mensaje.get("nombre", "Jugador")).strip()[:14] or "Jugador"

        if tipo == "create":
            codigo = nuevo_codigo()
            sala = Sala(codigo=codigo, host_id=str(uuid.uuid4()))
            salas[codigo] = sala
            jugador = Jugador(id=sala.host_id, nombre=nombre, ws=ws)
            sala.jugadores[jugador.id] = jugador
            await jugador.enviar(
                {
                    "type": "room_created",
                    "codigo": codigo,
                    "id": jugador.id,
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                    "host": sala.host_id,
                }
            )
        elif tipo == "practice":
            codigo = nuevo_codigo()
            sala = Sala(codigo=codigo, host_id=str(uuid.uuid4()), practica=True)
            salas[codigo] = sala
            jugador = Jugador(id=sala.host_id, nombre=nombre, ws=ws)
            sala.jugadores[jugador.id] = jugador
            await jugador.enviar(
                {
                    "type": "room_created",
                    "codigo": codigo,
                    "id": jugador.id,
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                    "host": sala.host_id,
                    "practica": True,
                }
            )
            sala.reiniciar_marcador()
            sala.cancelada = False
            sala.evento_cancelar.clear()
            sala.fase = "jugando"
            sala.tarea = asyncio.create_task(bucle_partida(sala))
        elif tipo == "cajas":
            codigo = nuevo_codigo()
            sala = Sala(codigo=codigo, host_id=str(uuid.uuid4()), modo="cajas")
            salas[codigo] = sala
            jugador = Jugador(id=sala.host_id, nombre=nombre, ws=ws)
            sala.jugadores[jugador.id] = jugador
            await jugador.enviar(
                {
                    "type": "room_created",
                    "codigo": codigo,
                    "id": jugador.id,
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                    "host": sala.host_id,
                    "modo": "cajas",
                }
            )
            sala.cancelada = False
            sala.evento_cancelar.clear()
            sala.fase = "jugando"
            sala.tarea = asyncio.create_task(bucle_cajas(sala))
        elif tipo == "fiesta":
            codigo = nuevo_codigo()
            sala = Sala(
                codigo=codigo,
                host_id=str(uuid.uuid4()),
                modo="fiesta",
                capacidad=MAX_MANDOS + 1,
            )
            salas[codigo] = sala
            jugador = Jugador(
                id=sala.host_id, nombre=nombre, ws=ws, rol="pantalla"
            )
            sala.jugadores[jugador.id] = jugador
            await jugador.enviar(
                {
                    "type": "room_created",
                    "codigo": codigo,
                    "id": jugador.id,
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                    "host": sala.host_id,
                    "modo": "fiesta",
                    "capacidad": sala.capacidad,
                }
            )
        elif tipo == "operaciones":
            codigo = nuevo_codigo()
            sala = Sala(
                codigo=codigo, host_id=str(uuid.uuid4()), modo="operaciones", capacidad=1
            )
            salas[codigo] = sala
            jugador = Jugador(id=sala.host_id, nombre=nombre, ws=ws)
            sala.jugadores[jugador.id] = jugador
            await jugador.enviar(
                {
                    "type": "room_created",
                    "codigo": codigo,
                    "id": jugador.id,
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                    "host": sala.host_id,
                    "modo": "operaciones",
                }
            )
            sala.cancelada = False
            sala.evento_cancelar.clear()
            sala.fase = "jugando"
            sala.tarea = asyncio.create_task(bucle_operaciones(sala))
        elif tipo == "individual":
            juegos = mensaje.get("juegos")
            juegos_validos = ("pajaros", "escritura", "cajas", "operaciones") + JUEGOS_MINI
            if not isinstance(juegos, list) or not juegos:
                await ws.send_json(
                    {"type": "error", "mensaje": "Elige al menos un juego"}
                )
                return
            # El orden canónico es el de la portada, sin duplicados.
            seleccion = [j for j in juegos_validos if j in juegos]
            if not seleccion:
                await ws.send_json(
                    {"type": "error", "mensaje": "Elige al menos un juego válido"}
                )
                return
            codigo = nuevo_codigo()
            sala = Sala(
                codigo=codigo,
                host_id=str(uuid.uuid4()),
                modo="individual",
                capacidad=1,
                practica=True,
                secuencia_individual=True,
                juegos_individual=seleccion,
            )
            salas[codigo] = sala
            jugador = Jugador(id=sala.host_id, nombre=nombre, ws=ws)
            sala.jugadores[jugador.id] = jugador
            await jugador.enviar(
                {
                    "type": "room_created",
                    "codigo": codigo,
                    "id": jugador.id,
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                    "host": sala.host_id,
                    "modo": "individual",
                    "practica": True,
                    "juegos": seleccion,
                }
            )
            sala.cancelada = False
            sala.evento_cancelar.clear()
            sala.fase = "jugando"
            sala.tarea = asyncio.create_task(bucle_individual(sala))
        elif tipo == "join":
            codigo = str(mensaje.get("codigo", "")).strip().upper()
            sala = salas.get(codigo)
            if sala is None:
                await ws.send_json({"type": "error", "mensaje": "Esa sala no existe"})
                return
            if len(sala.jugadores) >= sala.capacidad:
                await ws.send_json({"type": "error", "mensaje": "La sala está llena"})
                return
            if sala.fase != "lobby":
                await ws.send_json({"type": "error", "mensaje": "La partida ya empezó"})
                return
            rol = "mando" if sala.modo == "fiesta" else "jugador"
            jugador = Jugador(id=str(uuid.uuid4()), nombre=nombre, ws=ws, rol=rol)
            sala.jugadores[jugador.id] = jugador
            await jugador.enviar(
                {
                    "type": "room_joined",
                    "codigo": codigo,
                    "id": jugador.id,
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                    "host": sala.host_id,
                    "modo": sala.modo,
                    "rol": rol,
                    "capacidad": sala.capacidad,
                }
            )
            await sala.difundir(
                {
                    "type": "player_joined",
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                }
            )
        else:
            await ws.send_json({"type": "error", "mensaje": "Mensaje inicial desconocido"})
            return

        while True:
            datos = await ws.receive_json()
            if isinstance(datos, dict):
                await manejar_mensaje(sala, jugador, datos)

    except SalirSala:
        pass
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"[WS] {exc}")
    finally:
        if sala and jugador:
            sala.jugadores.pop(jugador.id, None)
            jugador.conectado = False
            # Si un mando se cae en fiesta, la partida sigue: solo se actualiza
            # la lista de conectados. Si se va la pantalla, sí se cancela todo.
            mando_fiesta = sala.modo == "fiesta" and jugador.rol == "mando"
            if not mando_fiesta and sala.fase not in ("lobby", "fin"):
                sala.cancelada = True
                sala.evento_cancelar.set()
            await sala.difundir(
                {
                    "type": "player_left"
                    if mando_fiesta or sala.fase in ("lobby", "fin", "resumen")
                    else "opponent_left",
                    "nombre": jugador.nombre,
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                }
            )
            if not sala.jugadores:
                salas.pop(sala.codigo, None)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
