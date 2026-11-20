"""Piezas comunes del árbitro: constantes, jugadores, salas y esperas."""
from __future__ import annotations

import asyncio
import contextlib
import random
import socket
import string
import traceback
from dataclasses import dataclass, field

from fastapi import WebSocket

from juego.minijuegos import JUEGOS_MINI, NOMBRES_MINI
from juego.reconocedor import Reconocedor, ReconocedorDigitos


# Datos que en FIESTA solo puede ver la pantalla: incluyen el marcador ajeno,
# los conteos de los demás o el desglose del podio.
CLAVES_SOLO_PANTALLA = frozenset(
    {"marcador", "conteos", "confirmados", "podio", "antes", "despues", "puntos_juego"}
)


JUEGOS = ("pajaros", "escritura")
# Fiesta: los juegos clásicos más los ocho minijuegos de entrenamiento.
# El host es la pantalla y hay hasta 8 mandos. «ppt» cierra la lista para fijar
# el orden de portada; se filtra de JUEGOS_MINI antes de añadirlo para que no
# aparezca dos veces.
JUEGOS_FIESTA = ("pajaros", "escritura", "cajas", "operaciones") + tuple(
    j for j in JUEGOS_MINI if j != "ppt"
) + ("ppt",)
NOMBRES_JUEGOS = {
    "pajaros": "HÁMSTERS",
    "escritura": "PALABRAS",
    "cajas": "CAJAS",
    "operaciones": "OPERACIONES",
    **NOMBRES_MINI,
}
TIEMPO_PODIO = 4.5
# Fiesta: el anfitrión elige en el lobby qué juegos se encadenan y, para cada
# uno, cuántas rondas y con qué dificultad.
DIFICULTADES_FIESTA = ("facil", "normal", "dificil")
RONDAS_FIESTA = 5
RONDAS_FIESTA_MAX = 20
VICTORIAS_NECESARIAS = 3
TIEMPO_CUENTA_PREVIA = 3.0

reconocedor = Reconocedor()
reconocedor_digitos = ReconocedorDigitos()
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
    juegos_fiesta: list[str] = field(default_factory=list)
    ajustes_fiesta: dict[str, dict] = field(default_factory=dict)
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
        """Difunde a todos, menos los datos compartidos a los mandos en FIESTA."""
        filtrar = self.modo == "fiesta" and any(
            clave in mensaje for clave in CLAVES_SOLO_PANTALLA
        )
        for jugador in list(self.jugadores.values()):
            if filtrar and jugador.rol == "mando":
                limpio = {
                    clave: valor
                    for clave, valor in mensaje.items()
                    if clave not in CLAVES_SOLO_PANTALLA
                }
                await jugador.enviar(limpio)
            else:
                await jugador.enviar(mensaje)


def ajuste_actual(sala: Sala) -> dict:
    """Rondas y dificultad que eligió el anfitrión para el juego en curso."""
    if sala.modo != "fiesta" or not sala.juego_fiesta:
        return {}
    return sala.ajustes_fiesta.get(sala.juego_fiesta, {})


def rondas_para(sala: Sala, defecto: int) -> int:
    """Rondas del juego actual: las del lobby en fiesta, si no las de siempre."""
    return ajuste_actual(sala).get("rondas", defecto)


def ronda_generador(sala: Sala, ronda: int, saltos: tuple[int, int, int]) -> int:
    """Ronda que ve el generador: la dificultad adelanta el punto de partida.

    Todos los generadores endurecen el reto con el número de ronda, así que
    NORMAL y DIFÍCIL empiezan ``saltos[1]`` / ``saltos[2]`` rondas más adelante
    y la progresión dentro del juego se conserva. Fuera de fiesta no cambia nada.
    """
    dificultad = ajuste_actual(sala).get("dificultad", "facil")
    return ronda + saltos[DIFICULTADES_FIESTA.index(dificultad)]


def leer_ajustes_fiesta(juegos, ajustes) -> tuple[list[str], dict[str, dict]]:
    """Valida la lista y los ajustes que manda el anfitrión (entrada no confiable)."""
    if not isinstance(juegos, list):
        return [], {}
    lista = list(dict.fromkeys(j for j in juegos if j in JUEGOS_FIESTA))
    ajustes = ajustes if isinstance(ajustes, dict) else {}
    limpios: dict[str, dict] = {}
    for juego in lista:
        dato = ajustes.get(juego)
        dato = dato if isinstance(dato, dict) else {}
        rondas = dato.get("rondas")
        if not isinstance(rondas, int) or isinstance(rondas, bool):
            rondas = RONDAS_FIESTA
        dificultad = dato.get("dificultad")
        limpios[juego] = {
            "rondas": max(1, min(RONDAS_FIESTA_MAX, rondas)),
            "dificultad": dificultad if dificultad in DIFICULTADES_FIESTA else "facil",
        }
    return lista, limpios


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
        # En fiesta se juega el juego actual; el número de rondas lo corta
        # bucle_partida según los ajustes del lobby.
        return sala.juego_fiesta
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


def lanzar(corrutina) -> asyncio.Task:
    """Arranca el bucle de una partida y registra si revienta (si no, falla mudo)."""
    tarea = asyncio.create_task(corrutina)

    def informar(t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception() is not None:
            traceback.print_exception(t.exception())

    tarea.add_done_callback(informar)
    return tarea


async def pausa(sala: Sala, segundos: float) -> None:
    await esperar(sala, asyncio.Event(), segundos)


def nombre_de(sala: "Sala", pid: str | None) -> str:
    """Nombre del jugador, aunque se haya desconectado a mitad de juego."""
    jugador = sala.jugadores.get(pid) if pid else None
    return jugador.nombre if jugador else "JUGADOR"


def participantes(sala: Sala) -> list[Jugador]:
    """Quienes juegan: en fiesta solo los mandos (la pantalla no puntúa)."""
    if sala.modo == "fiesta":
        return [j for j in sala.jugadores.values() if j.rol == "mando"]
    return list(sala.jugadores.values())


async def difundir_roles(
    sala: Sala, completo: dict, para_mandos: dict | None = None
) -> None:
    """En fiesta los mandos reciben una versión sin datos que deban memorizar."""
    # list(): un mando puede desconectarse mientras se espera un envío.
    for jugador in list(sala.jugadores.values()):
        mensaje = completo
        if sala.modo == "fiesta" and jugador.rol == "mando":
            mensaje = para_mandos if para_mandos is not None else completo
            # Ni siquiera la versión para el celular puede llevar marcadores.
            mensaje = {
                clave: valor
                for clave, valor in mensaje.items()
                if clave not in CLAVES_SOLO_PANTALLA
            }
        await jugador.enviar(mensaje)


async def difundir_a_pantalla(sala: Sala, mensaje: dict) -> None:
    """En FIESTA los datos compartidos los ve solo la pantalla del anfitrión."""
    # list(): un mando puede desconectarse mientras se espera un envío.
    for jugador in list(sala.jugadores.values()):
        if jugador.rol == "pantalla":
            await jugador.enviar(mensaje)


async def difundir_a_mandos(sala: Sala, mensaje: dict) -> None:
    """Avisos sin puntajes: el celular nunca recibe el marcador de los demás."""
    for jugador in list(sala.jugadores.values()):
        if jugador.rol == "mando":
            await jugador.enviar(mensaje)


async def emitir_progreso_vivo(
    sala: Sala, juego: str, filas: list[dict], ronda: int | None = None
) -> None:
    """Avance por ronda de cada mando: en vivo y solo en la pantalla."""
    await difundir_a_pantalla(
        sala,
        {
            "type": "progreso_vivo",
            "juego": juego,
            "ronda": ronda,
            "jugadores": filas,
        },
    )


def filas_avance_respuestas(sala: Sala, respondidos) -> list[dict]:
    """Quién ya respondió, sin revelar qué respondió."""
    return [
        {
            "id": j.id,
            "nombre": j.nombre,
            "avance": 1 if j.id in respondidos else 0,
            "total": 1,
            "estado": "listo" if j.id in respondidos else "esperando",
        }
        for j in participantes(sala)
    ]


def filas_avance_escritura(
    sala: Sala, juego: str, casillas: str, esperado: str
) -> list[dict]:
    """Casillas aceptadas de cada jugador, sin entregar la respuesta."""
    filas = []
    for jugador in participantes(sala):
        progreso = jugador.progreso or {}
        digitos = progreso.get(casillas, [])
        aceptadas = sum(1 for c in digitos if c.get("estado") == "aceptada")
        total = len(progreso.get(esperado, "")) or len(digitos)
        escribiendo = aceptadas or any(c.get("intentos") for c in digitos)
        filas.append(
            {
                "id": jugador.id,
                "nombre": jugador.nombre,
                "avance": aceptadas,
                "total": total,
                "estado": (
                    "listo"
                    if progreso.get("fin") is not None
                    else "contando"
                    if escribiendo
                    else "esperando"
                ),
            }
        )
    return filas


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


async def emitir_podium(
    sala: Sala, final: bool = False, siguiente: str | None = None
) -> None:
    """Muestra el podio animado; luego pasa al siguiente juego o vuelve al lobby."""
    for pid, puntos in sala.ultimos_puntos.items():
        sala.fiesta_puntos[pid] = sala.fiesta_puntos.get(pid, 0) + puntos
    filas = clasificacion(sala)
    antes = sala.podium_antes
    await difundir_a_pantalla(
        sala,
        {
            "type": "podium_final" if final else "podium_update",
            "antes": antes,
            "despues": filas,
            "puntos_juego": dict(sala.ultimos_puntos),
            "juego": sala.juego_fiesta,
            "nombre_juego": NOMBRES_JUEGOS.get(sala.juego_fiesta or "", ""),
            "siguiente": NOMBRES_JUEGOS.get(siguiente or "", ""),
        },
    )
    if final:
        sala.fase = "fin"
        # El celular solo necesita saber que terminó para poder volver al inicio.
        await difundir_a_mandos(sala, {"type": "fin_fiesta"})
        return
    await pausa(sala, TIEMPO_PODIO)
    sala.ultimos_puntos = {}
    if siguiente:
        return  # la lista sigue: el orquestador lanza el próximo juego
    sala.fase = "lobby"
    sala.juego_fiesta = None
    sala.tarea = None
    jugadores = {j.id: j.nombre for j in sala.jugadores.values()}
    await difundir_a_pantalla(
        sala,
        {
            "type": "back_to_selector",
            "podio": clasificacion(sala),
            "jugadores": jugadores,
            "host": sala.host_id,
        },
    )
    await difundir_a_mandos(
        sala,
        {"type": "back_to_selector", "jugadores": jugadores, "host": sala.host_id},
    )


def registrar_resultado_individual(sala: Sala, juego: str, datos: dict) -> None:
    """Guarda el resultado de un juego de la secuencia individual."""
    sala.resultados_individual[juego] = datos


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


async def reconocer_en_hilo(reconocer, trazos, casilla: dict) -> tuple[str, float]:
    """Corre el modelo fuera del bucle de eventos para no frenar al resto.

    ``procesando`` evita que dos envíos de la misma casilla se cuenten a la vez
    (el cliente ya bloquea el botón mientras espera, esto cubre a los tramposos).
    """
    casilla["procesando"] = True
    try:
        predicha, confianza, _ = await asyncio.to_thread(reconocer, trazos)
    finally:
        casilla["procesando"] = False
    return predicha, confianza
