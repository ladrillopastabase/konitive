"""Servidor de Konitive: salas, conexiones y despacho de mensajes.

Arrancar con::

    python servidor.py

El arbitraje de cada juego vive en el paquete ``arbitro``.
"""
from __future__ import annotations

import io
import time
import traceback
import uuid
from pathlib import Path

import qrcode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from qrcode.image.svg import SvgPathImage

from juego.minijuegos import JUEGOS_ESCRITURA, JUEGOS_MINI
from arbitro.nucleo import (
    JUEGOS_FIESTA,
    Jugador,
    Sala,
    SalirSala,
    difundir_a_mandos,
    difundir_a_pantalla,
    emitir_podium,
    emitir_progreso_vivo,
    filas_avance_respuestas,
    ip_local,
    lanzar,
    leer_ajustes_fiesta,
    nuevo_codigo,
    participantes,
    salas,
)
from arbitro.clasico import (
    ESCRITURA,
    bucle_partida,
    difundir_conteos,
    procesar_caracter,
)
from arbitro.cajas import bucle_cajas
from arbitro.operaciones import bucle_operaciones
from arbitro.minijuegos import manejar_respuesta_mini
from arbitro.rastreo import manejar_respuesta_rastreo
from arbitro.sesiones import bucle_fiesta, bucle_individual


BASE = Path(__file__).parent
ESTATICO = BASE / "static"
MAX_MANDOS = 8
# Tope de salas abiertas a la vez: evita que alguien llene la memoria creando
# salas en bucle si el servidor queda expuesto a Internet.
MAX_SALAS = 200
TIPOS_RESPUESTA_MINI = {
    **{f"{j}_answer": j for j in JUEGOS_MINI if j not in JUEGOS_ESCRITURA},
    **{f"{j}_digit": j for j in JUEGOS_ESCRITURA},
}
PUERTO = 6767
app = FastAPI(title="Konitive - Laboratorio de Atención")
app.mount("/static", StaticFiles(directory=ESTATICO), name="static")


async def manejar_mensaje(sala: Sala, jugador: Jugador, mensaje: dict) -> None:
    tipo = mensaje.get("type")

    if tipo == "start":
        if (
            jugador.id != sala.host_id
            or sala.fase != "lobby"
            or sala.tarea is not None
        ):
            return
        if sala.modo == "fiesta":
            # Lista de juegos y ajustes del lobby; "juego" suelto sigue valiendo.
            juegos = mensaje.get("juegos")
            if juegos is None and mensaje.get("juego") is not None:
                juegos = [mensaje.get("juego")]
            lista, ajustes = leer_ajustes_fiesta(juegos, mensaje.get("ajustes"))
            if not lista or not participantes(sala):
                return
            sala.juegos_fiesta = lista
            sala.ajustes_fiesta = ajustes
        elif len(sala.jugadores) < 2:
            return
        sala.reiniciar_marcador()
        sala.cancelada = False
        sala.evento_cancelar.clear()
        sala.fase = "jugando"
        if sala.modo == "fiesta":
            sala.tarea = lanzar(bucle_fiesta(sala))
        else:
            sala.tarea = lanzar(bucle_partida(sala))

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
            if sala.modo == "fiesta":
                jugadores = {j.id: j.nombre for j in sala.jugadores.values()}
                await difundir_a_pantalla(
                    sala,
                    {
                        "type": "back_to_lobby",
                        "marcador": sala.marcador(),
                        "jugadores": jugadores,
                        "host": sala.host_id,
                    },
                )
                await difundir_a_mandos(
                    sala,
                    {
                        "type": "back_to_lobby",
                        "jugadores": jugadores,
                        "host": sala.host_id,
                    },
                )
            else:
                await sala.difundir({"type": "back_to_lobby", "marcador": sala.marcador()})

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
            if sala.modo == "fiesta":
                # Solo se proyecta que ya contestó; el número elegido es secreto.
                await emitir_progreso_vivo(
                    sala,
                    "cajas",
                    filas_avance_respuestas(sala, sala.respuestas),
                    sala.datos.get("ronda"),
                )
            if len(sala.respuestas) >= len(participantes(sala)):
                sala.evento_respuestas.set()

    elif tipo == "cajas_restart":
        if sala.modo == "cajas" and sala.fase == "fin" and jugador.id == sala.host_id:
            sala.tarea = None
            sala.cancelada = False
            sala.evento_cancelar.clear()
            sala.fase = "jugando"
            sala.tarea = lanzar(bucle_cajas(sala))

    elif tipo == "rastreo_answer":
        await manejar_respuesta_rastreo(sala, jugador, mensaje)

    elif tipo in TIPOS_RESPUESTA_MINI:
        await manejar_respuesta_mini(sala, jugador, mensaje, TIPOS_RESPUESTA_MINI[tipo])

    elif tipo in ESCRITURA:
        await procesar_caracter(sala, jugador, mensaje, ESCRITURA[tipo])

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
            sala.tarea = lanzar(bucle_operaciones(sala))

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
            sala.tarea = lanzar(bucle_individual(sala))

    elif tipo == "continue_practice":
        if sala.practica and sala.fase == "resumen":
            sala.fase = "jugando"
            sala.evento_continuar.set()

    elif tipo == "leave":
        raise SalirSala()


JUEGOS_INDIVIDUAL = JUEGOS_FIESTA  # mismos juegos y mismo orden de portada
# Mensaje inicial -> (opciones de la sala, bucle que arranca solo o None si hay lobby).
SALAS_NUEVAS = {
    "create": ({}, None),
    "practice": ({"practica": True}, bucle_partida),
    "cajas": ({"modo": "cajas"}, bucle_cajas),
    "fiesta": ({"modo": "fiesta", "capacidad": MAX_MANDOS + 1}, None),
    "operaciones": ({"modo": "operaciones", "capacidad": 1}, bucle_operaciones),
    "individual": (
        {
            "modo": "individual",
            "capacidad": 1,
            "practica": True,
            "secuencia_individual": True,
        },
        bucle_individual,
    ),
}


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
        nombre = str(mensaje.get("nombre", "Paciente")).strip()[:14] or "Paciente"

        if tipo in SALAS_NUEVAS:
            if len(salas) >= MAX_SALAS:
                await ws.send_json(
                    {"type": "error", "mensaje": "Servidor lleno, prueba en un rato"}
                )
                return
            opciones, bucle = SALAS_NUEVAS[tipo]
            seleccion: list[str] = []
            if tipo == "individual":
                juegos = mensaje.get("juegos")
                if not isinstance(juegos, list) or not juegos:
                    await ws.send_json({"type": "error", "mensaje": "Elige al menos un juego"})
                    return
                # El orden canónico es el de la portada, sin duplicados.
                seleccion = [j for j in JUEGOS_INDIVIDUAL if j in juegos]
                if not seleccion:
                    await ws.send_json(
                        {"type": "error", "mensaje": "Elige al menos un juego válido"}
                    )
                    return
            codigo = nuevo_codigo()
            sala = Sala(
                codigo=codigo,
                host_id=str(uuid.uuid4()),
                juegos_individual=seleccion,
                **opciones,
            )
            salas[codigo] = sala
            rol = "pantalla" if sala.modo == "fiesta" else "jugador"
            jugador = Jugador(id=sala.host_id, nombre=nombre, ws=ws, rol=rol)
            sala.jugadores[jugador.id] = jugador
            await jugador.enviar(
                {
                    "type": "room_created",
                    "codigo": codigo,
                    "id": jugador.id,
                    "jugadores": {j.id: j.nombre for j in sala.jugadores.values()},
                    "host": sala.host_id,
                    "modo": sala.modo,
                    "practica": sala.practica,
                    "capacidad": sala.capacidad,
                    "juegos": seleccion,
                }
            )
            if bucle is not None:
                # Modos de una sola persona: la partida arranca sin lobby.
                sala.fase = "jugando"
                sala.tarea = lanzar(bucle(sala))
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
    except Exception:
        traceback.print_exc()
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

    # Un dibujo válido (20 trazos x 400 puntos) cabe de sobra en 256 KB.
    uvicorn.run(app, host="0.0.0.0", port=PUERTO, ws_max_size=256 * 1024)
