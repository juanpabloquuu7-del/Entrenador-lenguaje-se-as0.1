"""
test_tts.py
Prueba el motor de voz: lista voces disponibles y pronuncia ejemplos.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pyttsx3
import time
from core.tts_engine import TTSEngine


def listar_voces():
    engine = pyttsx3.init()
    voces = engine.getProperty("voices")
    print(f"\nVoces disponibles en este sistema ({len(voces)}):")
    for i, voz in enumerate(voces):
        print(f"  [{i}] ID: {voz.id}")
        print(f"       Nombre: {voz.name}")
        print(f"       Idiomas: {voz.languages}")
    engine.stop()


def main():
    listar_voces()

    print("\nProbando TTSEngine...")
    tts = TTSEngine()

    print("→ Pronunciando letras individuales: H, O, L, A")
    for letra in ["H", "O", "L", "A"]:
        tts.speak_letter(letra)
        time.sleep(0.8)

    time.sleep(0.5)
    print("→ Pronunciando frase completa: 'Hola, bienvenidos al traductor de Lengua de Señas Colombiana'")
    tts.speak_phrase("Hola, bienvenidos al traductor de Lengua de Señas Colombiana")
    time.sleep(4)

    print("\nPrueba completada.")


if __name__ == "__main__":
    main()
