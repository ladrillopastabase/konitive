"""Catálogo único de pruebas: orden de portada, nombre, descripción y dificultades.

Es la única lista de juegos del proyecto. El árbitro la usa para validar el
lobby y nombrar el podio, y el cliente la recibe en ``GET /api/juegos`` para
pintar el selector INDIVIDUAL, la lista de FIESTA y los títulos.

Para añadir un juego: una entrada aquí, su generador en ``juego/``, su bucle
en ``arbitro/`` (registrado en ``arbitro.sesiones.BUCLES``) y su archivo en
``static/juegos/``.
"""
from __future__ import annotations

DIFICULTADES = ("facil", "normal", "dificil")

CATALOGO: tuple[dict, ...] = (
    {
        "id": "pajaros",
        "nombre": "HÁMSTERS",
        "descripcion": "Cuenta los hámsters en cuanto aparecen y confirma el total: agudizas la atención de Conita para no perder detalle.",
    },
    {
        "id": "escritura",
        "nombre": "PALABRAS",
        "descripcion": "Memoriza la palabra que parpadea y escríbela letra a letra: fortaleces la memoria de Conita y su precisión.",
    },
    {
        "id": "cajas",
        "nombre": "CAJAS",
        "descripcion": "Cuenta todas las cajas de la pila, también las que quedan escondidas: entrenas la visión espacial de Conita.",
    },
    {
        "id": "operaciones",
        "nombre": "OPERACIONES",
        "descripcion": "Recuerda la operación apenas un instante y escribe el resultado cifra a cifra: ejercitas la memoria de trabajo y el cálculo de Conita.",
    },
    {
        "id": "stroop",
        "nombre": "STROOP",
        "descripcion": "Nombra el color de la tinta, no lo que dice la palabra: ayudas a Conita a ignorar distracciones y responder más rápido.",
    },
    {
        "id": "triangulos",
        "nombre": "TRIÁNGULOS",
        "descripcion": "Resuelve mentalmente las operaciones de la fila y escribe el resultado final: estimulas el cálculo de Conita.",
    },
    {
        "id": "relojes",
        "nombre": "RELOJES",
        "descripcion": "Calcula cuánto tiempo pasó entre dos relojes y escribe horas y minutos: afinas la noción del tiempo de Conita.",
    },
    {
        "id": "menor",
        "nombre": "MENOR A MAYOR",
        "descripcion": "Toca los números en orden ascendente: mejoras la atención selectiva y la rapidez de decisión de Conita.",
    },
    {
        "id": "memoria",
        "nombre": "MEMORIA",
        "descripcion": "Memoriza la grilla y toca las casillas en orden: amplías la capacidad de memoria de Conita.",
    },
    {
        "id": "vuelto",
        "nombre": "DAR VUELTO",
        "descripcion": "Arma el vuelto exacto con billetes y monedas: practicas el cálculo mental de Conita en una compra real.",
    },
    {
        "id": "silabas",
        "nombre": "SÍLABAS",
        "descripcion": "Cuenta las sílabas de la frase y escribe el total: ejercitas la lectura atenta y la concentración de Conita.",
    },
    {
        "id": "rastreo",
        "nombre": "RASTREO DE HÁMSTERS",
        "descripcion": "Sigue los dos hámsters entre los gatos mientras el tablero se mueve: fortaleces la memoria visual de Conita.",
        "dificultades": DIFICULTADES + ("experto",),
    },
    {
        "id": "ppt",
        "nombre": "PIEDRA · PAPEL · TIJERA",
        "descripcion": "Lee la consigna y elige una mano que gane o pierda a propósito: entrenas el autocontrol de Conita.",
    },
)

# Las dificultades por defecto se rellenan aquí para no repetirlas en cada entrada.
for _juego in CATALOGO:
    _juego.setdefault("dificultades", DIFICULTADES)

IDS: tuple[str, ...] = tuple(j["id"] for j in CATALOGO)
NOMBRES: dict[str, str] = {j["id"]: j["nombre"] for j in CATALOGO}
POR_ID: dict[str, dict] = {j["id"]: j for j in CATALOGO}
