"""El desglose único del cliente: tiempo, errores y puntuación."""
from __future__ import annotations

from apoyo import RAIZ  # primero: deja la raíz del proyecto en sys.path

import subprocess


CODIGO = r"""
global.window = global;
const codigo = require('fs').readFileSync('static/desgloses.js', 'utf8');
new Function(codigo)();
process.stdout.write(JSON.stringify([
  textoDesglose({ tiempo: 2, errores: 1, puntuacion: 7 }),
  textoDesglose({}),
  textoDesglose({ tiempo: 1.256, errores: 2, puntuacion: 11.256 }),
  textoDesglose({ tiempo_total: 12, errores: 2, puntuacion: 22 }),
  numero(12.3 + 4.1),
]));
"""


def probar_texto_desglose() -> None:
    resultado = subprocess.run(
        ["node", "-e", CODIGO],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    import json

    completo, vacio, decimales, informe, suma = json.loads(resultado.stdout)
    assert completo == "TIEMPO 2 s · ERRORES 1 · PUNTUACIÓN 7", completo
    assert vacio == "TIEMPO 0 s · ERRORES 0 · PUNTUACIÓN 0", vacio
    assert decimales == "TIEMPO 1.26 s · ERRORES 2 · PUNTUACIÓN 11.26", decimales
    assert suma == "16.4", suma  # nunca 16.400000000000002
    assert informe == "TIEMPO 12 s · ERRORES 2 · PUNTUACIÓN 22", informe


def main() -> None:
    probar_texto_desglose()
    print("OK - Desglose único TIEMPO / ERRORES / PUNTUACIÓN")


if __name__ == "__main__":
    main()
