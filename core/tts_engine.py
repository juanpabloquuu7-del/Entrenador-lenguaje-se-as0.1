"""
tts_engine.py
Motor de Texto a Voz en español usando pyttsx3.
Todas las llamadas de audio corren en un hilo separado para no bloquear la GUI.
"""

import pyttsx3
import threading


class TTSEngine:
    def __init__(self):
        self._engine = pyttsx3.init()
        self._lock = threading.Lock()
        self._configurar_voz_espanol()

    def _configurar_voz_espanol(self):
        voces = self._engine.getProperty("voices")
        voz_es = None
        for voz in voces:
            identificador = (voz.id + voz.name).lower()
            if any(tag in identificador for tag in ("es_", "es-", "spanish", "español", "sabina", "helena", "jorge", "pablo")):
                voz_es = voz.id
                break

        if voz_es:
            self._engine.setProperty("voice", voz_es)
        # Si no encuentra voz en español usa la del sistema por defecto

        self._engine.setProperty("rate", 150)   # velocidad natural
        self._engine.setProperty("volume", 1.0)

    def speak(self, texto):
        """Pronuncia cualquier texto en un hilo separado."""
        if not texto or not texto.strip():
            return
        threading.Thread(target=self._hablar, args=(texto,), daemon=True).start()

    def speak_letter(self, letra):
        """Pronuncia una letra individual."""
        self.speak(letra)

    def speak_phrase(self, frase):
        """Pronuncia la frase completa acumulada en la pizarra."""
        self.speak(frase)

    def _hablar(self, texto):
        with self._lock:
            try:
                engine = pyttsx3.init()
                self._configurar_voz_en_instancia(engine)
                engine.say(texto)
                engine.runAndWait()
                engine.stop()
            except Exception:
                pass  # No interrumpir la GUI si el TTS falla

    def _configurar_voz_en_instancia(self, engine):
        """Aplica la misma configuración de voz a una instancia nueva del hilo."""
        voces = engine.getProperty("voices")
        for voz in voces:
            identificador = (voz.id + voz.name).lower()
            if any(tag in identificador for tag in ("es_", "es-", "spanish", "español", "sabina", "helena", "jorge", "pablo")):
                engine.setProperty("voice", voz.id)
                break
        engine.setProperty("rate", 150)
        engine.setProperty("volume", 1.0)
