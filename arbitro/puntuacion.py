"""Puntuación compartida por las 13 pruebas.

puntuación = tiempo + 5 s por error. Es el único resultado, en segundos y
menor es mejor: no hay escala invertida ni puntos acumulables.
"""
from __future__ import annotations

SEGUNDOS_POR_ERROR = 5.0


def puntuacion(tiempo_total: float, errores_totales: int) -> float:
    """Tiempo total con penalizaciones, en segundos con dos decimales; menor es mejor."""
    return round(tiempo_total + SEGUNDOS_POR_ERROR * errores_totales, 2)


def fallos_escritura(casillas: list[dict], incompleto: bool = False) -> int:
    """Cuenta los caracteres rechazados antes de aceptar cada casilla.

    La aceptación automática tras 3 intentos implica 3 rechazos; una casilla
    aceptada tras corregir cuenta todos menos el intento final correcto.
    """
    fallos = 0
    for casilla in casillas:
        intentos = casilla.get("intentos", 0)
        motivo = casilla.get("motivo", "")
        if casilla.get("estado") != "aceptada" or motivo == "automatica":
            fallos += intentos
        elif motivo == "primera":
            continue
        else:
            fallos += max(0, intentos - 1)
    if incompleto:
        fallos += 1
    return fallos


def sumar_puntuacion(
    historial: list[dict], pid: str, tiempo: float, errores: int
) -> float:
    """Acumula tiempo y errores previos y devuelve la puntuación total."""
    tiempo_total = tiempo
    errores_totales = errores
    for entrada in historial:
        tiempos = entrada.get("tiempo", 0.0)
        fallos = entrada.get("errores", 0)
        if isinstance(tiempos, dict):
            # Historial de los clásicos: un mapa por jugador, como los tiempos.
            tiempo_total += tiempos.get(pid, 0.0)
            if isinstance(fallos, dict):
                errores_totales += fallos.get(pid, 0)
        elif entrada.get("pid", entrada.get("jugador")) == pid:
            tiempo_total += tiempos
            if not isinstance(fallos, dict):
                errores_totales += fallos
    return puntuacion(tiempo_total, errores_totales)
