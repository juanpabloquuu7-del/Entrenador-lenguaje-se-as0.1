"""
test_detector.py
Prueba rápida del HandDetector. Abre la cámara y muestra el esqueleto en pantalla.
Presiona 'q' para salir.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
from core.hand_detector import HandDetector


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: No se detectó ninguna cámara.")
        return

    detector = HandDetector()
    print("Cámara abierta. Muestra tu mano. Presiona 'q' para salir.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        landmarks_norm, landmarks_raw = detector.process(frame)
        detector.draw(frame, landmarks_raw)

        if landmarks_norm is not None:
            cv2.putText(frame, f"Landmarks: {len(landmarks_norm)} valores", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            # Mostrar los primeros 6 valores del vector normalizado
            preview = [f"{v:.3f}" for v in landmarks_norm[:6]]
            cv2.putText(frame, f"Vec: {preview}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        else:
            cv2.putText(frame, "Coloque su mano frente a la camara", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow("Test HandDetector - LSC", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    detector.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
