"""
hand_detector.py
Extrae y normaliza los 21 landmarks de la mano usando MediaPipe Tasks API.
Compatible con mediapipe 0.10.30+
"""

import mediapipe as mp
import cv2
import os

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "hand_landmarker.task")

BaseOptions        = mp.tasks.BaseOptions
HandLandmarker     = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode        = mp.tasks.vision.RunningMode

# Conexiones para dibujar el esqueleto (índices de landmarks)
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),
    (9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),
    (0,17)
]


class HandDetector:
    def __init__(self, min_detection_confidence=0.7, min_tracking_confidence=0.7):
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_tracking_confidence,
        )
        self._landmarker = HandLandmarker.create_from_options(options)

    def process(self, frame_bgr):
        """
        Procesa un frame BGR de OpenCV.

        Retorna:
            landmarks_norm (list[float] | None): Vector de 63 valores normalizados o None.
            landmarks_raw (list | None): Lista de 21 puntos (x,y) en píxeles para dibujar.
        """
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result    = self._landmarker.detect(mp_image)

        if not result.hand_landmarks:
            return None, None

        landmarks = result.hand_landmarks[0]  # primera mano
        landmarks_norm = self._normalize(landmarks)

        h, w = frame_bgr.shape[:2]
        landmarks_px = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

        return landmarks_norm, landmarks_px

    def draw(self, frame_bgr, landmarks_px):
        """Dibuja el esqueleto de la mano sobre el frame (in-place)."""
        if landmarks_px is None:
            return
        for start, end in HAND_CONNECTIONS:
            cv2.line(frame_bgr, landmarks_px[start], landmarks_px[end],
                     (0, 255, 0), 2)
        for x, y in landmarks_px:
            cv2.circle(frame_bgr, (x, y), 4, (255, 255, 255), -1)

    def _normalize(self, landmarks):
        """
        Normaliza los 21 landmarks restando la muñeca (landmark 0)
        y escala por la distancia muñeca-dedo medio para ser invariante
        al tamaño de la mano en pantalla.
        Resultado: vector de 60 floats (x, y de landmarks 1..20).
        """
        ox, oy, oz = landmarks[0].x, landmarks[0].y, landmarks[0].z

        # Escala: distancia entre muñeca (0) y base del dedo medio (9)
        dx = landmarks[9].x - ox
        dy = landmarks[9].y - oy
        escala = max((dx**2 + dy**2) ** 0.5, 1e-6)

        vector = []
        for lm in landmarks[1:]:
            vector.extend([
                (lm.x - ox) / escala,
                (lm.y - oy) / escala,
                (lm.z - oz) / escala,   # profundidad normalizada
            ])
        return vector

    def close(self):
        self._landmarker.close()
