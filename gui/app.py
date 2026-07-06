"""
app.py
Ventana principal del Traductor LSC.
Feed de cámara en tiempo real + pizarra acumulativa + TTS.
"""

import tkinter as tk
from tkinter import messagebox
import cv2
import os
import sys
import time
from PIL import Image, ImageTk

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.hand_detector import HandDetector
from core.classifier import Classifier, MODEL_NOT_FOUND
from core.tts_engine import TTSEngine

# ---------------------------------------------------------------- Constantes
CAM_W, CAM_H     = 640, 480
COOLDOWN_SEG     = 1.5   # segundos entre adiciones de la misma letra
ESPACIO_SEG      = 2.0   # segundos sin mano para insertar espacio
COLOR_BG         = "#1e1e2e"
COLOR_FG         = "#cdd6f4"
COLOR_ACENTO     = "#89b4fa"
COLOR_OK         = "#a6e3a1"
COLOR_WARN       = "#f9e2af"
COLOR_PIZARRA_BG = "#181825"
CAMERA_INDICES   = (0, 1, 2, 3)


class AppWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Traductor LSC — Lengua de Señas Colombiana")
        self.root.resizable(False, False)
        self.root.configure(bg=COLOR_BG)

        self.detector   = HandDetector()
        self.classifier = Classifier()
        self.tts        = TTSEngine()

        self.pizarra        = ""
        self._ultima_letra  = None
        self._t_ultima_add  = 0.0
        self._t_sin_mano    = None   # timestamp desde que no hay mano
        self._espacio_puesto = False  # evita poner múltiples espacios seguidos

        self._build_ui()
        self._verificar_modelo()
        self._abrir_camara()
        self._loop_camara()

    # ------------------------------------------------------------------- UI --

    def _build_ui(self):
        # ── Feed de cámara ──────────────────────────────────────────────────
        self.lbl_camara = tk.Label(self.root, bg="#000000")
        self.lbl_camara.grid(row=0, column=0, columnspan=4,
                             padx=10, pady=(10, 4))
        self.lbl_camara.configure(
            text="Iniciando cámara...",
            fg=COLOR_FG, font=("Segoe UI", 14, "bold"), compound="center")

        # ── Letra detectada ─────────────────────────────────────────────────
        frame_letra = tk.Frame(self.root, bg=COLOR_BG)
        frame_letra.grid(row=1, column=0, columnspan=4, pady=4)

        tk.Label(frame_letra, text="Letra detectada:", bg=COLOR_BG,
                 fg=COLOR_FG, font=("Segoe UI", 12)).pack(side="left", padx=(0, 8))

        self.lbl_letra = tk.Label(frame_letra, text="—",
                                  bg=COLOR_BG, fg=COLOR_ACENTO,
                                  font=("Segoe UI", 72, "bold"), width=2)
        self.lbl_letra.pack(side="left")

        self.lbl_confianza = tk.Label(frame_letra, text="",
                                      bg=COLOR_BG, fg=COLOR_FG,
                                      font=("Segoe UI", 12))
        self.lbl_confianza.pack(side="left", padx=(12, 0))

        # ── Pizarra ──────────────────────────────────────────────────────────
        tk.Label(self.root, text="PIZARRA", bg=COLOR_BG, fg=COLOR_ACENTO,
                 font=("Segoe UI", 10, "bold")).grid(
            row=2, column=0, columnspan=4, sticky="w", padx=16)

        self.lbl_pizarra = tk.Label(
            self.root, text="", bg=COLOR_PIZARRA_BG, fg=COLOR_OK,
            font=("Segoe UI", 28, "bold"), anchor="w",
            width=28, height=2, wraplength=580, justify="left",
            relief="flat", padx=12, pady=8)
        self.lbl_pizarra.grid(row=3, column=0, columnspan=4,
                               padx=10, pady=(0, 6), sticky="ew")

        # ── Botones ──────────────────────────────────────────────────────────
        btn_cfg = {"font": ("Segoe UI", 11, "bold"), "cursor": "hand2",
                   "padx": 10, "pady": 6, "relief": "flat", "bd": 0}

        self.btn_leer = tk.Button(
            self.root, text="🔊  Leer Frase",
            bg=COLOR_ACENTO, fg=COLOR_BG, activebackground="#74c7ec",
            command=self._leer_frase, **btn_cfg)
        self.btn_leer.grid(row=4, column=0, padx=(10, 4), pady=4, sticky="ew")

        self.btn_borrar = tk.Button(
            self.root, text="⌫  Borrar",
            bg="#fab387", fg=COLOR_BG, activebackground="#f38ba8",
            command=self._borrar_ultimo, **btn_cfg)
        self.btn_borrar.grid(row=4, column=1, padx=4, pady=4, sticky="ew")

        self.btn_limpiar = tk.Button(
            self.root, text="🗑  Limpiar",
            bg="#f38ba8", fg=COLOR_BG, activebackground="#eba0ac",
            command=self._limpiar_pizarra, **btn_cfg)
        self.btn_limpiar.grid(row=4, column=2, padx=4, pady=4, sticky="ew")

        self.btn_entrenador = tk.Button(
            self.root, text="⚙  Modo Entrenador",
            bg="#585b70", fg=COLOR_FG, activebackground="#6c7086",
            command=self._abrir_entrenador, **btn_cfg)
        self.btn_entrenador.grid(row=4, column=3, padx=(4, 10), pady=4, sticky="ew")

        # ── Mensaje de estado ────────────────────────────────────────────────
        self.lbl_estado = tk.Label(
            self.root, text="", bg=COLOR_BG, fg=COLOR_WARN,
            font=("Segoe UI", 10), wraplength=620)
        self.lbl_estado.grid(row=5, column=0, columnspan=4,
                              padx=10, pady=(2, 10))

        # Pesos de columnas para que los botones se distribuyan igual
        for c in range(4):
            self.root.columnconfigure(c, weight=1)

    # ─────────────────────────────────────────────────── Cámara y detección --

    def _abrir_camara(self):
        self.cap = None
        for idx in CAMERA_INDICES:
            for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    self.cap = cap
                    self.lbl_camara.configure(text="")
                    self.lbl_estado.configure(
                        text=f"Cámara activa en dispositivo {idx}.", fg=COLOR_OK)
                    return
                cap.release()

        self.lbl_camara.configure(text="No se pudo abrir la cámara", fg="#f38ba8")
        messagebox.showerror(
            "Sin cámara",
            "Error: No se detectó ninguna cámara.\n"
            "Conecte una cámara web e intente de nuevo.")

    def _loop_camara(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                landmarks_norm, landmarks_raw = self.detector.process(frame)
                self.detector.draw(frame, landmarks_raw)
                self._procesar_prediccion(landmarks_norm)

                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img).resize((CAM_W, CAM_H))
                self._photo = ImageTk.PhotoImage(img)
                self.lbl_camara.configure(image=self._photo)
                self.lbl_camara.configure(text="")
            else:
                self.lbl_camara.configure(
                    text="La cámara está abierta, pero no entrega frames.",
                    fg=COLOR_WARN)
        else:
            self.lbl_camara.configure(text="Esperando cámara...", fg=COLOR_WARN)

        self.root.after(30, self._loop_camara)

    def _procesar_prediccion(self, landmarks_norm):
        if not self.classifier.listo:
            return

        if landmarks_norm is None:
            # Sin mano en frame
            self.classifier.limpiar_buffer()
            self.lbl_letra.configure(text="—", fg=COLOR_ACENTO)
            self.lbl_confianza.configure(text="")
            self.lbl_estado.configure(
                text="Coloque su mano frente a la cámara", fg=COLOR_WARN)
            self._manejar_espacio_automatico(mano_presente=False)
            return

        self._t_sin_mano = None
        self._espacio_puesto = False

        confirmada, instantanea, confianza = self.classifier.predecir(landmarks_norm)

        # Actualizar UI con predicción instantánea
        if instantanea:
            self.lbl_letra.configure(text=instantanea, fg=COLOR_ACENTO)
            self.lbl_confianza.configure(
                text=f"{confianza*100:.0f}%",
                fg=COLOR_OK if confianza >= 0.80 else COLOR_WARN)
            self.lbl_estado.configure(text="", fg=COLOR_FG)
        else:
            self.lbl_letra.configure(text="?", fg="#585b70")
            self.lbl_confianza.configure(
                text="Seña no reconocida con certeza. Intente de nuevo.",
                fg=COLOR_WARN)
            self.lbl_estado.configure(text="", fg=COLOR_FG)

        # Agregar a pizarra solo si la letra está confirmada por el buffer
        if confirmada:
            self._intentar_agregar(confirmada)

    def _manejar_espacio_automatico(self, mano_presente):
        if mano_presente:
            self._t_sin_mano = None
            return

        ahora = time.time()
        if self._t_sin_mano is None:
            self._t_sin_mano = ahora
            return

        if (ahora - self._t_sin_mano) >= ESPACIO_SEG and not self._espacio_puesto:
            if self.pizarra and not self.pizarra.endswith(" "):
                self.pizarra += " "
                self._espacio_puesto = True
                self._actualizar_pizarra()

    def _intentar_agregar(self, letra):
        ahora = time.time()
        mismo_cooldown = (
            letra == self._ultima_letra and
            (ahora - self._t_ultima_add) < COOLDOWN_SEG
        )
        if mismo_cooldown:
            return

        self.pizarra += letra
        self._ultima_letra = letra
        self._t_ultima_add = ahora
        self._actualizar_pizarra()
        self.tts.speak_letter(letra)

    # ──────────────────────────────────────────────────────── Pizarra ──────

    def _actualizar_pizarra(self):
        texto = self.pizarra if self.pizarra else ""
        self.lbl_pizarra.configure(text=texto)

    def _leer_frase(self):
        if self.pizarra.strip():
            self.tts.speak_phrase(self.pizarra.strip())
        else:
            self.lbl_estado.configure(
                text="La pizarra está vacía.", fg=COLOR_WARN)

    def _borrar_ultimo(self):
        if self.pizarra:
            self.pizarra = self.pizarra[:-1]
            self._actualizar_pizarra()

    def _limpiar_pizarra(self):
        self.pizarra = ""
        self._ultima_letra = None
        self._actualizar_pizarra()

    # ──────────────────────────────────────────────────── Modo Entrenador ──

    def _abrir_entrenador(self):
        from gui.trainer import TrainerWindow
        ventana = tk.Toplevel(self.root)
        app = TrainerWindow(ventana)
        ventana.protocol("WM_DELETE_WINDOW", app.cerrar)
        # Al cerrar el entrenador, recargar el modelo por si fue reentrenado
        ventana.bind("<Destroy>", lambda e: self.classifier.recargar())

    # ──────────────────────────────────────────────────── Verificaciones ──

    def _verificar_modelo(self):
        if not self.classifier.listo:
            if self.classifier.error == MODEL_NOT_FOUND:
                self.lbl_estado.configure(
                    text="Modelo no encontrado. Use el Modo Entrenador "
                         "para crear su dataset y entrenar el sistema.",
                    fg=COLOR_WARN)
            else:
                self.lbl_estado.configure(
                    text=self.classifier.error, fg="#f38ba8")

    # ──────────────────────────────────────────────────────────── Cierre ──

    def cerrar(self):
        if self.cap:
            self.cap.release()
        self.detector.close()
        self.root.destroy()


def abrir_app():
    root = tk.Tk()
    app = AppWindow(root)
    root.protocol("WM_DELETE_WINDOW", app.cerrar)
    root.mainloop()


if __name__ == "__main__":
    abrir_app()
