"""
trainer.py
Modo Entrenador — Captura landmarks de LSC y los guarda en data/dataset.csv.
Incluye botón para entrenar el modelo directamente desde la interfaz.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import threading
import csv
import os
import time
from PIL import Image, ImageTk
import sys

# Ruta base del proyecto (funciona tanto en desarrollo como empaquetado)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "dataset.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")

sys.path.insert(0, BASE_DIR)
from core.hand_detector import HandDetector


COLUMNAS = ["letra"] + [f"{eje}{i}" for i in range(1, 21) for eje in ("x", "y", "z")]

CAPTURE_COUNTDOWN = 3   # segundos de cuenta regresiva
CAPTURE_DURATION  = 5   # segundos de captura activa
CAPTURE_RATE_MS   = 100 # intervalo entre muestras (10 muestras/seg)
CAMERA_INDICES    = (0, 1, 2, 3)


class TrainerWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Modo Entrenador — LSC")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        self.detector = HandDetector()
        self.cap = None
        self.running = False

        self._estado = "idle"          # idle | countdown | capturing
        self._countdown_val = 0
        self._capture_start = 0.0
        self._muestras_sesion = 0
        self._letra_actual = ""

        self._build_ui()
        self._abrir_camara()
        self._loop_camara()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        # Feed de cámara
        self.lbl_camara = tk.Label(self.root, bg="#000000")
        self.lbl_camara.grid(row=0, column=0, columnspan=3, padx=10, pady=10)
        self.lbl_camara.configure(
            text="Iniciando cámara...",
            fg="#cdd6f4", font=("Segoe UI", 14, "bold"), compound="center")

        # Fila: etiqueta letra
        tk.Label(self.root, text="Letra a capturar:", bg="#1e1e2e",
                 fg="#cdd6f4", font=("Segoe UI", 12)).grid(
            row=1, column=0, padx=(10, 4), pady=4, sticky="e")

        self.entry_letra = tk.Entry(self.root, font=("Segoe UI", 14, "bold"),
                                    width=4, justify="center")
        self.entry_letra.grid(row=1, column=1, padx=4, pady=4, sticky="w")
        self.entry_letra.bind("<KeyRelease>", self._forzar_mayuscula)

        self.btn_capturar = tk.Button(
            self.root, text="▶  Iniciar Captura",
            font=("Segoe UI", 11, "bold"), bg="#89b4fa", fg="#1e1e2e",
            activebackground="#74c7ec", cursor="hand2",
            command=self._iniciar_captura, padx=10, pady=6)
        self.btn_capturar.grid(row=1, column=2, padx=10, pady=4)

        # Estado / contador
        self.lbl_estado = tk.Label(
            self.root, text="Listo para capturar.",
            bg="#1e1e2e", fg="#a6e3a1", font=("Segoe UI", 11), wraplength=580)
        self.lbl_estado.grid(row=2, column=0, columnspan=3, padx=10, pady=2)

        # Barra de progreso
        self.progress = ttk.Progressbar(self.root, length=580, mode="determinate")
        self.progress.grid(row=3, column=0, columnspan=3, padx=10, pady=4)

        # Contadores
        self.lbl_contadores = tk.Label(
            self.root, text="Muestras esta sesión: 0  |  Total en dataset: 0",
            bg="#1e1e2e", fg="#cdd6f4", font=("Segoe UI", 10))
        self.lbl_contadores.grid(row=4, column=0, columnspan=3, padx=10, pady=2)

        # Botón entrenar
        self.btn_entrenar = tk.Button(
            self.root, text="🧠  Entrenar Modelo Ahora",
            font=("Segoe UI", 11, "bold"), bg="#a6e3a1", fg="#1e1e2e",
            activebackground="#94e2d5", cursor="hand2",
            command=self._entrenar, padx=10, pady=6)
        self.btn_entrenar.grid(row=5, column=0, columnspan=3, padx=10, pady=(6, 12))

        self._actualizar_contadores()

    # --------------------------------------------------------- Cámara loop --

    def _abrir_camara(self):
        self.cap = None
        for idx in CAMERA_INDICES:
            for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    self.cap = cap
                    self.lbl_camara.configure(text="")
                    self.lbl_estado.configure(
                        text=f"Cámara activa en dispositivo {idx}.", fg="#a6e3a1")
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
                self._ultimo_landmarks = landmarks_norm

                # Overlay de estado sobre el frame
                self._dibujar_overlay(frame)

                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img).resize((580, 435))
                self._photo = ImageTk.PhotoImage(img)
                self.lbl_camara.configure(image=self._photo)
                self.lbl_camara.configure(text="")
            else:
                self.lbl_camara.configure(
                    text="La cámara está abierta, pero no entrega frames.",
                    fg="#f9e2af")
        else:
            self.lbl_camara.configure(text="Esperando cámara...", fg="#f9e2af")

        self.root.after(30, self._loop_camara)

    def _dibujar_overlay(self, frame):
        if self._estado == "countdown":
            texto = f"Preparate... {self._countdown_val}"
            cv2.putText(frame, texto, (160, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 200, 255), 4)

        elif self._estado == "capturing":
            elapsed = time.time() - self._capture_start
            restante = max(0, CAPTURE_DURATION - elapsed)
            texto = f"Capturando '{self._letra_actual}'... {restante:.1f}s"
            cv2.putText(frame, texto, (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 100), 2)
            cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]),
                          (0, 255, 100), 4)

    # ---------------------------------------------------- Lógica captura --

    def _forzar_mayuscula(self, event=None):
        val = self.entry_letra.get().upper()
        self.entry_letra.delete(0, tk.END)
        self.entry_letra.insert(0, val[:1])  # solo 1 carácter

    def _iniciar_captura(self):
        letra = self.entry_letra.get().strip().upper()
        if not letra:
            messagebox.showwarning("Letra vacía",
                                   "Escriba la letra que va a señar antes de capturar.")
            return
        if self._estado != "idle":
            return

        self._letra_actual = letra
        self._muestras_sesion = 0
        self.btn_capturar.configure(state="disabled")
        self._iniciar_countdown(CAPTURE_COUNTDOWN)

    def _iniciar_countdown(self, segundos):
        self._estado = "countdown"
        self._countdown_val = segundos
        self.lbl_estado.configure(
            text=f"Prepárese para señar la letra '{self._letra_actual}'...",
            fg="#f9e2af")
        self._tick_countdown()

    def _tick_countdown(self):
        if self._countdown_val > 0:
            self._countdown_val -= 1
            self.root.after(1000, self._tick_countdown)
        else:
            self._comenzar_captura()

    def _comenzar_captura(self):
        self._estado = "capturing"
        self._capture_start = time.time()
        self.progress["value"] = 0
        self.lbl_estado.configure(
            text=f"Capturando señas para '{self._letra_actual}'...",
            fg="#a6e3a1")
        self._tick_captura()

    def _tick_captura(self):
        elapsed = time.time() - self._capture_start
        progreso = min(100, (elapsed / CAPTURE_DURATION) * 100)
        self.progress["value"] = progreso

        if elapsed < CAPTURE_DURATION:
            landmarks = getattr(self, "_ultimo_landmarks", None)
            if landmarks is not None:
                self._guardar_muestra(self._letra_actual, landmarks)
                self._muestras_sesion += 1
                self._actualizar_contadores()
            self.root.after(CAPTURE_RATE_MS, self._tick_captura)
        else:
            self._finalizar_captura()

    def _finalizar_captura(self):
        self._estado = "idle"
        self.progress["value"] = 100
        total = self._contar_total()
        self.lbl_estado.configure(
            text=f"✅ Captura finalizada. "
                 f"Muestras para '{self._letra_actual}': {self._muestras_sesion}  |  "
                 f"Total en dataset: {total}",
            fg="#a6e3a1")
        self.btn_capturar.configure(state="normal")

    # ---------------------------------------------------- Dataset CSV --

    def _guardar_muestra(self, letra, landmarks):
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        archivo_nuevo = not os.path.exists(DATA_PATH)
        with open(DATA_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if archivo_nuevo:
                writer.writerow(COLUMNAS)
            writer.writerow([letra] + landmarks)

    def _contar_total(self):
        if not os.path.exists(DATA_PATH):
            return 0
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)  # descontar encabezado

    def _actualizar_contadores(self):
        total = self._contar_total()
        self.lbl_contadores.configure(
            text=f"Muestras esta sesión: {self._muestras_sesion}  |  "
                 f"Total en dataset: {total}")

    # ---------------------------------------------------- Entrenamiento --

    def _entrenar(self):
        if not os.path.exists(DATA_PATH):
            messagebox.showwarning(
                "Sin datos",
                "No se encontró dataset.csv.\n"
                "Capture señas primero antes de entrenar.")
            return

        self.btn_entrenar.configure(state="disabled",
                                    text="⏳  Entrenando...")
        self.lbl_estado.configure(text="Entrenando modelo, espere...",
                                  fg="#f9e2af")

        def _hilo():
            try:
                import subprocess
                train_script = os.path.join(BASE_DIR, "train.py")
                resultado = subprocess.run(
                    [sys.executable, train_script],
                    capture_output=True, text=True, encoding="latin-1")
                salida = resultado.stdout.strip() or resultado.stderr.strip()
            except Exception as e:
                salida = f"Error al entrenar: {e}"
            self.root.after(0, lambda: self._post_entrenamiento(salida))

        threading.Thread(target=_hilo, daemon=True).start()

    def _post_entrenamiento(self, mensaje):
        self.btn_entrenar.configure(state="normal",
                                    text="🧠  Entrenar Modelo Ahora")
        self.lbl_estado.configure(text=mensaje, fg="#a6e3a1")
        messagebox.showinfo("Entrenamiento", mensaje)

    # ---------------------------------------------------------- Cierre --

    def cerrar(self):
        if self.cap:
            self.cap.release()
        self.detector.close()
        self.root.destroy()


def abrir_trainer():
    root = tk.Tk()
    app = TrainerWindow(root)
    root.protocol("WM_DELETE_WINDOW", app.cerrar)
    root.mainloop()


if __name__ == "__main__":
    abrir_trainer()
