"""
classifier.py
Carga el modelo lsc_model.pkl y predice la letra con filtro de estabilización (smoothing).
"""

import os
import joblib
from collections import deque

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "lsc_model.pkl")

MODEL_NOT_FOUND = "MODEL_NOT_FOUND"

BUFFER_SIZE    = 15   # últimas N predicciones
MIN_VOTES      = 10   # mínimo de votos para confirmar una letra (66%)
MIN_CONFIDENCE = 0.60 # confianza mínima del modelo para considerar la predicción


class Classifier:
    def __init__(self):
        self._modelo = None
        self._buffer = deque(maxlen=BUFFER_SIZE)
        self._error = None
        self._cargar_modelo()

    def _cargar_modelo(self):
        if not os.path.exists(MODEL_PATH):
            self._error = MODEL_NOT_FOUND
            return
        try:
            self._modelo = joblib.load(MODEL_PATH)
        except Exception as e:
            self._error = f"Error al cargar modelo: {e}"

    @property
    def listo(self):
        return self._modelo is not None

    @property
    def error(self):
        return self._error

    def recargar(self):
        """Vuelve a intentar cargar el modelo (útil tras entrenar desde el Modo Entrenador)."""
        self._error = None
        self._modelo = None
        self._buffer.clear()
        self._cargar_modelo()

    def predecir(self, landmarks_vector):
        """
        Recibe el vector de 63 floats normalizados.

        Retorna:
            letra_confirmada (str | None): Letra estable según el buffer, o None.
            letra_instantanea (str | None): Predicción del frame actual (para mostrar en UI).
            confianza (float): Score de confianza del frame actual (0.0 – 1.0).
        """
        if not self.listo:
            return None, None, 0.0

        X = [landmarks_vector]
        proba = self._modelo.predict_proba(X)[0]
        idx_max = proba.argmax()
        confianza = proba[idx_max]
        letra_instantanea = self._modelo.classes_[idx_max]

        if confianza < MIN_CONFIDENCE:
            self._buffer.append(None)
            return None, None, confianza

        self._buffer.append(letra_instantanea)

        # Contar votos en el buffer
        votos = sum(1 for v in self._buffer if v == letra_instantanea)
        letra_confirmada = letra_instantanea if votos >= MIN_VOTES else None

        return letra_confirmada, letra_instantanea, confianza

    def limpiar_buffer(self):
        self._buffer.clear()
