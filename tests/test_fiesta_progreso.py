"""El avance en vivo y el podio son exclusivos de la pantalla en FIESTA.

Comprueba que los mandos nunca reciben marcadores, conteos ni avances ajenos,
y que el progreso de los minijuegos va privadamente a cada celular sin filtrar
la respuesta correcta.
"""
from __future__ import annotations

from apoyo import cliente_js, conectar, levantar_servidor  # primero: deja la raíz del proyecto en sys.path

import asyncio
import json
import time

import websockets

import servidor
from arbitro import nucleo


async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)


nucleo.pausa = pausa_corta

URL = levantar_servidor()
CLAVES_AJENAS = (
    "marcador", "conteos", "confirmados", "podio", "antes", "despues",
    "puntos_juego", "puntuacion_juego",
)


def sin_datos_ajenos(cliente):
    for mensaje in cliente.recibidos:
        for clave in CLAVES_AJENAS:
            assert clave not in mensaje, (clave, mensaje)


async def main():
    host = await conectar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]
    mandos = [
        await conectar({"type": "join", "nombre": nombre, "codigo": codigo})
        for nombre in ("Ana", "Beto")
    ]

    await host.enviar(
        {
            "type": "start",
            "juegos": ["pajaros"],
            "ajustes": {"pajaros": {"rondas": 1, "dificultad": "facil"}},
        }
    )
    show = await host.esperar("birds_show")
    await host.esperar("birds_hide")
    for mando in mandos:
        mando_show = await mando.esperar("birds_show")
        await mando.enviar(
            {
                "type": "bird_answer",
                "count": len(show["aves"]),
                "token": mando_show["token"],
            }
        )

    avance = await host.esperar("progreso_vivo")
    assert avance["juego"] == "pajaros", avance
    assert len(avance["jugadores"]) == 2, avance
    assert all(fila["total"] is None for fila in avance["jugadores"]), avance
    for mando in mandos:
        assert not mando.de_tipo("progreso_vivo"), mando.de_tipo("progreso_vivo")
        sin_datos_ajenos(mando)

    podio = await host.esperar("podium_update")
    assert podio["nombre_juego"] == "HÁMSTERS", podio
    for mando in mandos:
        assert not mando.de_tipo("podium_update"), mando.de_tipo("podium_update")
        propio = await mando.esperar("mi_puntuacion")
        pid = mando.recibidos[0]["id"]
        assert propio["puntuacion"] == podio["puntuacion_juego"][pid], propio
        assert propio["puesto"] in (1, 2), propio
        assert propio["total"] == 2, propio
        assert propio["juego"] == "pajaros", propio
        assert "despues" not in propio and "puntuacion_juego" not in propio, propio
        assert "puntos" not in propio, propio
        await mando.esperar("back_to_selector")
    await host.esperar("back_to_selector")

    await host.enviar(
        {
            "type": "start",
            "juegos": ["stroop"],
            "ajustes": {"stroop": {"rondas": 1, "dificultad": "facil"}},
        }
    )
    show_stroop = await host.esperar("stroop_show")
    write = await host.esperar("stroop_write")
    for mando in mandos:
        await mando.enviar(
            {
                "type": "stroop_answer",
                "ronda": write["ronda"],
                "respuesta": show_stroop["tinta"],
            }
        )
    await asyncio.sleep(0.1)

    # El avance del minijuego se proyecta agregado; el detalle es privado.
    assert not host.de_tipo("mini_progreso"), host.de_tipo("mini_progreso")
    for mando in mandos:
        progresos = mando.de_tipo("mini_progreso")
        assert len(progresos) == 1, progresos
        assert "acepta" not in progresos[0], progresos[0]
        assert progresos[0]["pid"] == mando.recibidos[0]["id"], progresos[0]
        sin_datos_ajenos(mando)

    avances_stroop = [m for m in host.de_tipo("progreso_vivo") if m["juego"] == "stroop"]
    assert avances_stroop, host.de_tipo("progreso_vivo")
    texto = json.dumps(avances_stroop, ensure_ascii=False)
    assert show_stroop["tinta"] not in texto, (show_stroop, texto)
    assert show_stroop.get("palabra") not in texto, (show_stroop, texto)

    podio2 = await host.esperar("podium_update")
    acumulado = {f["id"]: f["puntuacion"] for f in podio2["despues"]}
    for mando in mandos:
        await mando.esperar("mi_puntuacion", desde=1)
        assert len(mando.de_tipo("mi_puntuacion")) == 2
        assert mando.de_tipo("mi_puntuacion")[-1]["puntuacion"] == acumulado[
            mando.recibidos[0]["id"]
        ]
    await host.enviar({"type": "finish_fiesta"})
    await host.esperar("podium_final")
    for mando in mandos:
        assert not mando.de_tipo("podium_final"), mando.de_tipo("podium_final")
        podio_celular = await mando.esperar("podio_mando")
        assert podio_celular["final"] is True, podio_celular
        assert len(podio_celular["filas"]) == 2, podio_celular
        assert {f["id"] for f in podio_celular["filas"]} == set(acumulado)
        assert "puntuacion_juego" not in podio_celular, podio_celular
        assert all("puntos" not in fila for fila in podio_celular["filas"])
        await mando.esperar("fin_fiesta")

    js = cliente_js()
    assert 'case "mi_puntuacion"' in js
    assert 'case "podio_mando"' in js

    for cliente in (host, *mandos):
        await cliente.cerrar()
    await asyncio.sleep(0.1)
    assert not servidor.salas, f"Quedaron salas abiertas: {list(servidor.salas)}"
    print("OK - Puntuación propia y podio final en el mando; secretos solo en pantalla")


if __name__ == "__main__":
    asyncio.run(main())
