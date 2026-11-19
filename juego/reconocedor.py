"""Reconocimiento de letras y dígitos manuscritos con modelos ONNX.

``emnist_model.onnx`` (26 clases A-Z) reconoce letras; ``mnist_model.onnx``
(10 clases 0-9) reconoce dígitos. Ambos vienen del proyecto
https://github.com/adiagarwalrock/mnist-digits-web y comparten el preprocesado
de su ``web/app.js``: el navegador solo envía los trazos normalizados y el
árbitro decide si el carácter es válido. La diferencia es que EMNIST guarda las
imágenes transpuestas y MNIST no, además del formato de entrada.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw

Punto = tuple[float, float]
Trazo = Sequence[Punto]

MODELO = Path(__file__).parent / "modelos" / "emnist_model.onnx"
MODELO_DIGITOS = Path(__file__).parent / "modelos" / "mnist_model.onnx"
TAMANO_CANVAS = 280
GROSOR_TRAZO = 22
LADO_IMAGEN = 28
LADO_TRAZO = 20
UMBRAL_TINTA = 0.08


def _probabilidades(valores: np.ndarray) -> np.ndarray:
    """Aplica softmax solo si la salida no parece ya una distribución."""
    v = np.asarray(valores, dtype=np.float64)
    if np.all(v >= 0) and v.max() <= 1.0001 and abs(float(v.sum()) - 1.0) < 0.01:
        return v
    exponentes = np.exp(v - v.max())
    return exponentes / exponentes.sum()


class Reconocedor:
    def __init__(self, ruta_modelo: str | Path = MODELO) -> None:
        self.sesion = ort.InferenceSession(
            str(ruta_modelo), providers=["CPUExecutionProvider"]
        )
        self.nombre_entrada = self.sesion.get_inputs()[0].name
        self.nombre_salida = self.sesion.get_outputs()[0].name

    def _rasterizar(self, trazos: Sequence[Trazo], tamano: int = TAMANO_CANVAS) -> np.ndarray:
        """Convierte los trazos normalizados (0..1) en una imagen 28x28 de tinta."""
        imagen = Image.new("L", (tamano, tamano), 255)
        dibujo = ImageDraw.Draw(imagen)
        radio = GROSOR_TRAZO // 2

        for trazo in trazos:
            puntos = [
                (int(round(x * tamano)), int(round(y * tamano)))
                for x, y in trazo
                if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
            ]
            if not puntos:
                continue
            if len(puntos) > 1:
                dibujo.line(puntos, fill=0, width=GROSOR_TRAZO, joint="curve")
            for x, y in puntos:
                dibujo.ellipse((x - radio, y - radio, x + radio, y + radio), fill=0)

        pequena = imagen.resize((LADO_IMAGEN, LADO_IMAGEN), Image.Resampling.LANCZOS)
        return 1.0 - (np.asarray(pequena, dtype=np.float32) / 255.0)

    @staticmethod
    def _normalizar(tinta: np.ndarray) -> np.ndarray:
        """Recorta al trazo, escala a 20x20 y centra en 28x28 (estilo MNIST)."""
        ys, xs = np.nonzero(tinta > UMBRAL_TINTA)
        if len(xs) == 0:
            return tinta

        min_x, max_x = int(xs.min()), int(xs.max())
        min_y, max_y = int(ys.min()), int(ys.max())
        ancho = max_x - min_x + 1
        alto = max_y - min_y + 1
        escala = LADO_TRAZO / max(ancho, alto)
        dibujo_ancho = max(1, round(ancho * escala))
        dibujo_alto = max(1, round(alto * escala))
        inicio_x = (LADO_IMAGEN - dibujo_ancho) // 2
        inicio_y = (LADO_IMAGEN - dibujo_alto) // 2

        salida = np.zeros((LADO_IMAGEN, LADO_IMAGEN), dtype=np.float32)
        for y in range(dibujo_alto):
            sy = min_y + min(alto - 1, int(y / escala))
            for x in range(dibujo_ancho):
                sx = min_x + min(ancho - 1, int(x / escala))
                salida[inicio_y + y, inicio_x + x] = tinta[sy, sx]
        return salida

    def _preprocesar(self, trazos: Sequence[Trazo]) -> np.ndarray:
        tinta = self._rasterizar(trazos)
        normalizada = self._normalizar(tinta)
        # EMNIST guarda las imágenes transpuestas; sin esto el modelo falla.
        return normalizada.T.reshape(1, 784).astype(np.float32)

    def _inferir(self, entrada: np.ndarray) -> tuple[str, float, list[float]]:
        crudos = self.sesion.run(
            [self.nombre_salida], {self.nombre_entrada: entrada}
        )[0][0]
        probs = _probabilidades(crudos)
        indice = int(np.argmax(probs))
        return chr(65 + indice), float(probs[indice]), [float(p) for p in probs]

    def reconocer(self, trazos: Sequence[Trazo]) -> tuple[str, float, list[float]]:
        """Reconoce una letra a partir de los trazos del canvas del navegador."""
        return self._inferir(self._preprocesar(trazos))

    def reconocer_tinta(self, tinta: np.ndarray) -> tuple[str, float, list[float]]:
        """Reconoce una letra desde una matriz 28x28 de tinta (para pruebas)."""
        return self._inferir(
            self._normalizar(tinta).T.reshape(1, 784).astype(np.float32)
        )


class ReconocedorDigitos(Reconocedor):
    """Reconoce cifras manuscritas con el modelo MNIST de 10 clases.

    Comparte el rasterizado y el centrado estilo MNIST con el reconocedor de
    letras. MNIST no transpone la imagen y su modelo espera ``[1, 1, 28, 28]``.
    """

    def __init__(self, ruta_modelo: str | Path = MODELO_DIGITOS) -> None:
        super().__init__(ruta_modelo)

    def _preprocesar(self, trazos: Sequence[Trazo]) -> np.ndarray:
        tinta = self._rasterizar(trazos)
        normalizada = self._normalizar(tinta)
        return normalizada.reshape(1, 1, LADO_IMAGEN, LADO_IMAGEN).astype(np.float32)

    def _inferir(self, entrada: np.ndarray) -> tuple[str, float, list[float]]:
        crudos = self.sesion.run(
            [self.nombre_salida], {self.nombre_entrada: entrada}
        )[0][0]
        probs = _probabilidades(crudos)
        indice = int(np.argmax(probs))
        return str(indice), float(probs[indice]), [float(p) for p in probs]

    def reconocer_tinta(self, tinta: np.ndarray) -> tuple[str, float, list[float]]:
        """Reconoce una cifra desde una matriz 28x28 de tinta (para pruebas)."""
        return self._inferir(
            self._normalizar(tinta)
            .reshape(1, 1, LADO_IMAGEN, LADO_IMAGEN)
            .astype(np.float32)
        )
