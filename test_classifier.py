"""
test_classifier.py
Prueba el Classifier en tiempo real con la cámara.
Muestra la letra instantánea, la letra confirmada y la confianza.
Presiona 'q' para salir.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
from core.hand_detector import HandDetector
from core.classifier import Classifier, MODEL_NOT_FOUND


def main():
    detector   = HandDetector()
    classifier = Classifier()

    if not classifier.listo:
        if classifier.error == MODEL_NOT_FOUND:
            print("Modelo no encontrado. Use el Modo Entrenador para crear su dataset y entrenar el sistema.")
        else:
            print(classifier.error)
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: No se detectó ninguna cámara.")
        return

    print("Clasificador listo. Muestra tu mano. Presiona 'q' para salir.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        landmarks_norm, landmarks_raw = detector.process(frame)
        detector.draw(frame, landmarks_raw)

        if landmarks_norm is not None:
            confirmada, instantanea, confianza = classifier.predecir(landmarks_norm)

            # Letra instantánea (gris)
            cv2.putText(frame, f"Detectando: {instantanea or '?'}  ({confianza*100:.0f}%)",
                        (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 180, 180), 2)

            # Letra confirmada (verde grande)
            if confirmada:
                cv2.putText(frame, confirmada, (280, 200),
                            cv2.FONT_HERSHEY_SIMPLEX, 6, (0, 255, 100), 8)
        else:
            classifier.limpiar_buffer()
            cv2.putText(frame, "Coloque su mano frente a la camara",
                        (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow("Test Classifier — LSC", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    detector.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
```
