"""
app.py
Traductor LSC para aulas — interfaz principal.
Estudiante hace señas → letras forman palabras → voz las lee para el profesor.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import cv2, os, sys, time, datetime
from PIL import Image, ImageTk

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.hand_detector import HandDetector
from core.classifier    import Classifier, MODEL_NOT_FOUND
from core.tts_engine    import TTSEngine

# ── Constantes ────────────────────────────────────────────────────────────────
CAM_W, CAM_H   = 640, 480
COOLDOWN_SEG   = 1.5
PAUSA_PALABRA  = 2.0
PAUSA_FRASE    = 5.0

COLOR_BG       = "#1e1e2e"
COLOR_FG       = "#cdd6f4"
COLOR_ACENTO   = "#89b4fa"
COLOR_OK       = "#a6e3a1"
COLOR_WARN     = "#f9e2af"
COLOR_PIZARRA  = "#181825"
COLOR_HISTORIAL= "#11111b"
CAMERA_INDICES = (0, 1, 2, 3)


class AppWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Traductor LSC — Lengua de Señas Colombiana")
        self.root.resizable(False, False)
        self.root.configure(bg=COLOR_BG)

        self.detector   = HandDetector()
        self.classifier = Classifier()
        self.tts        = TTSEngine()

        self.palabra_actual  = ""
        self.frase_actual    = ""
        self.historial       = []

        self._ultima_letra   = None
        self._t_ultima_add   = 0.0
        self._t_sin_mano     = None
        self._palabra_leida  = False
        self._frase_leida    = False
        self._modo_practica  = False
        self._votos_buffer   = 0

        self._ventana_profesor = None

        self._build_ui()
        self._verificar_modelo()
        self._abrir_camara()
        self._loop_camara()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Cámara
        self.lbl_camara = tk.Label(self.root, bg="#000000")
        self.lbl_camara.grid(row=0, column=0, columnspan=5,
                             padx=10, pady=(10, 4))
        self.lbl_camara.configure(text="Iniciando cámara...",
                                  fg=COLOR_FG, font=("Segoe UI", 14, "bold"),
                                  compound="center")

        # Letra + confianza + voz
        frame_letra = tk.Frame(self.root, bg=COLOR_BG)
        frame_letra.grid(row=1, column=0, columnspan=5, pady=(4, 0))

        tk.Label(frame_letra, text="Detectando:",
                 bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 11)).pack(side="left", padx=(0, 8))

        self.lbl_letra = tk.Label(frame_letra, text="—",
                                  bg=COLOR_BG, fg=COLOR_ACENTO,
                                  font=("Segoe UI", 64, "bold"), width=2)
        self.lbl_letra.pack(side="left")

        self.lbl_confianza = tk.Label(frame_letra, text="",
                                      bg=COLOR_BG, fg=COLOR_FG,
                                      font=("Segoe UI", 11))
        self.lbl_confianza.pack(side="left", padx=(10, 0))

        self.lbl_voz = tk.Label(frame_letra, text="🎤 Esperando...",
                                bg=COLOR_BG, fg="#585b70",
                                font=("Segoe UI", 10, "bold"))
        self.lbl_voz.pack(side="right", padx=(0, 10))

        # Barra de estabilización
        tk.Label(self.root, text="Estabilidad de seña:",
                 bg=COLOR_BG, fg="#585b70",
                 font=("Segoe UI", 8)).grid(
            row=2, column=0, columnspan=5, sticky="w", padx=16, pady=(4, 0))

        self.barra_confianza = ttk.Progressbar(
            self.root, length=640, mode="determinate", maximum=100)
        self.barra_confianza.grid(row=3, column=0, columnspan=5,
                                  padx=10, pady=(0, 4))

        # Modo práctica toggle
        self.var_practica = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.root, text="🎯 Modo Práctica (no acumula letras)",
            variable=self.var_practica, command=self._toggle_practica,
            bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_BG,
            activebackground=COLOR_BG, activeforeground=COLOR_ACENTO,
            font=("Segoe UI", 9)).grid(
            row=4, column=0, columnspan=5, sticky="w", padx=16, pady=(0, 4))

        # Palabra en curso
        frame_palabra = tk.Frame(self.root, bg=COLOR_BG)
        frame_palabra.grid(row=5, column=0, columnspan=5,
                           padx=10, pady=(0, 2), sticky="ew")
        tk.Label(frame_palabra, text="PALABRA:",
                 bg=COLOR_BG, fg=COLOR_ACENTO,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 6))
        self.lbl_palabra = tk.Label(frame_palabra, text="",
                                    bg=COLOR_PIZARRA, fg="#cba6f7",
                                    font=("Segoe UI", 22, "bold"),
                                    anchor="w", padx=10, pady=4, width=30)
        self.lbl_palabra.pack(side="left", fill="x", expand=True)

        # Frase en curso
        frame_frase = tk.Frame(self.root, bg=COLOR_BG)
        frame_frase.grid(row=6, column=0, columnspan=5,
                         padx=10, pady=(0, 2), sticky="ew")
        tk.Label(frame_frase, text="FRASE:  ",
                 bg=COLOR_BG, fg=COLOR_ACENTO,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 6))
        self.lbl_frase = tk.Label(frame_frase, text="",
                                  bg=COLOR_PIZARRA, fg=COLOR_OK,
                                  font=("Segoe UI", 20, "bold"),
                                  anchor="w", padx=10, pady=4,
                                  width=30, wraplength=560)
        self.lbl_frase.pack(side="left", fill="x", expand=True)

        # Historial
        tk.Label(self.root, text="HISTORIAL DE LA SESIÓN",
                 bg=COLOR_BG, fg="#585b70",
                 font=("Segoe UI", 8, "bold")).grid(
            row=7, column=0, columnspan=5, sticky="w", padx=16, pady=(6, 0))

        self.txt_historial = scrolledtext.ScrolledText(
            self.root, height=4, bg=COLOR_HISTORIAL, fg=COLOR_FG,
            font=("Segoe UI", 11), state="disabled",
            relief="flat", padx=8, pady=6, wrap="word")
        self.txt_historial.grid(row=8, column=0, columnspan=5,
                                padx=10, pady=(0, 6), sticky="ew")

        # Botones fila 1
        btn_cfg = {"font": ("Segoe UI", 10, "bold"), "cursor": "hand2",
                   "padx": 8, "pady": 5, "relief": "flat", "bd": 0}

        tk.Button(self.root, text="🔊 Leer Frase",
                  bg=COLOR_ACENTO, fg=COLOR_BG,
                  command=self._leer_frase_manual, **btn_cfg).grid(
            row=9, column=0, padx=(10, 4), pady=2, sticky="ew")

        tk.Button(self.root, text="⌫ Borrar Letra",
                  bg="#fab387", fg=COLOR_BG,
                  command=self._borrar_letra, **btn_cfg).grid(
            row=9, column=1, padx=4, pady=2, sticky="ew")

        tk.Button(self.root, text="✂ Borrar Palabra",
                  bg="#f9e2af", fg=COLOR_BG,
                  command=self._borrar_palabra, **btn_cfg).grid(
            row=9, column=2, padx=4, pady=2, sticky="ew")

        tk.Button(self.root, text="🗑 Limpiar Todo",
                  bg="#f38ba8", fg=COLOR_BG,
                  command=self._limpiar_todo, **btn_cfg).grid(
            row=9, column=3, padx=4, pady=2, sticky="ew")

        tk.Button(self.root, text="⚙ Entrenador",
                  bg="#585b70", fg=COLOR_FG,
                  command=self._abrir_entrenador, **btn_cfg).grid(
            row=9, column=4, padx=(4, 10), pady=2, sticky="ew")

        # Botones fila 2
        tk.Button(self.root, text="💾 Exportar Historial",
                  bg="#313244", fg=COLOR_FG,
                  command=self._exportar_historial, **btn_cfg).grid(
            row=10, column=0, columnspan=2, padx=(10, 4), pady=2, sticky="ew")

        tk.Button(self.root, text="📺 Pantalla Profesor",
                  bg="#313244", fg=COLOR_FG,
                  command=self._abrir_pantalla_profesor, **btn_cfg).grid(
            row=10, column=2, columnspan=3, padx=(4, 10), pady=2, sticky="ew")

        # Estado
        self.lbl_estado = tk.Label(self.root, text="",
                                   bg=COLOR_BG, fg=COLOR_WARN,
                                   font=("Segoe UI", 9), wraplength=660)
        self.lbl_estado.grid(row=11, column=0, columnspan=5,
                             padx=10, pady=(0, 8))

        for c in range(5):
            self.root.columnconfigure(c, weight=1)

    # ── Cámara ────────────────────────────────────────────────────────────────

    def _abrir_camara(self):
        self.cap = None
        for idx in CAMERA_INDICES:
            for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    self.cap = cap
                    self.lbl_camara.configure(text="")
                    self.lbl_estado.configure(text="Cámara activa.", fg=COLOR_OK)
                    return
                cap.release()
        messagebox.showerror("Sin cámara",
                             "No se detectó ninguna cámara.\n"
                             "Conecte una cámara web e intente de nuevo.")

    def _loop_camara(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                landmarks_norm, landmarks_raw = self.detector.process(frame)
                self.detector.draw(frame, landmarks_raw)
                self._procesar_prediccion(landmarks_norm)
                img = Image.fromarray(
                    cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((CAM_W, CAM_H))
                self._photo = ImageTk.PhotoImage(img)
                self.lbl_camara.configure(image=self._photo, text="")
        self.root.after(30, self._loop_camara)

    # ── Detección ─────────────────────────────────────────────────────────────

    def _procesar_prediccion(self, landmarks_norm):
        if not self.classifier.listo:
            return

        if landmarks_norm is None:
            self.classifier.limpiar_buffer()
            self.lbl_letra.configure(text="—", fg=COLOR_ACENTO)
            self.lbl_confianza.configure(text="")
            self.barra_confianza["value"] = 0
            self.lbl_estado.configure(
                text="Coloque su mano frente a la cámara", fg=COLOR_WARN)
            self._manejar_pausa(mano=False)
            return

        self._manejar_pausa(mano=True)
        confirmada, instantanea, confianza = self.classifier.predecir(landmarks_norm)

        # Barra de estabilización basada en votos del buffer
        self.barra_confianza["value"] = confianza * 100

        if instantanea:
            self.lbl_letra.configure(text=instantanea, fg=COLOR_ACENTO)
            self.lbl_confianza.configure(
                text=f"{confianza*100:.0f}%",
                fg=COLOR_OK if confianza >= 0.80 else COLOR_WARN)
            self.lbl_estado.configure(text="", fg=COLOR_FG)

            # Modo práctica: solo muestra, no acumula
            if self._modo_practica:
                feedback = "✅ ¡Seña reconocida!" if confirmada else "👀 Mantenga la seña..."
                self.lbl_estado.configure(
                    text=f"{feedback}  Letra: {instantanea}  Confianza: {confianza*100:.0f}%",
                    fg=COLOR_OK if confirmada else COLOR_WARN)
                return
        else:
            self.lbl_letra.configure(text="?", fg="#585b70")
            self.lbl_confianza.configure(
                text="Seña no reconocida. Intente de nuevo.", fg=COLOR_WARN)

        if confirmada and not self._modo_practica:
            self._agregar_letra(confirmada)

    # ── Palabras y frases ─────────────────────────────────────────────────────

    def _agregar_letra(self, letra):
        ahora = time.time()
        if (letra == self._ultima_letra and
                ahora - self._t_ultima_add < COOLDOWN_SEG):
            return
        self.palabra_actual += letra
        self._ultima_letra   = letra
        self._t_ultima_add   = ahora
        self._palabra_leida  = False
        self._frase_leida    = False
        self.lbl_palabra.configure(text=self.palabra_actual)
        self.lbl_voz.configure(text="🖐 Señando...", fg=COLOR_OK)
        self._actualizar_profesor()

    def _manejar_pausa(self, mano):
        if mano:
            self._t_sin_mano = None
            return

        ahora = time.time()
        if self._t_sin_mano is None:
            self._t_sin_mano = ahora
            return

        espera = ahora - self._t_sin_mano

        if espera < PAUSA_PALABRA:
            if self.palabra_actual:
                self.lbl_voz.configure(
                    text=f"⏳ Leyendo en {PAUSA_PALABRA - espera:.1f}s...",
                    fg=COLOR_WARN)
            return

        # Pausa corta → confirmar palabra
        if not self._palabra_leida and self.palabra_actual:
            palabra = self.palabra_actual.strip()
            self.frase_actual = (self.frase_actual + " " + palabra).strip()
            self.lbl_frase.configure(text=self.frase_actual)
            self.tts.speak_phrase(palabra)
            self.lbl_voz.configure(text=f"🔊 {palabra}", fg=COLOR_ACENTO)
            self.palabra_actual = ""
            self.lbl_palabra.configure(text="")
            self._palabra_leida = True
            self._actualizar_profesor()

        # Pausa larga → confirmar frase
        if espera >= PAUSA_FRASE and not self._frase_leida and self.frase_actual:
            self._guardar_en_historial(self.frase_actual)
            self.frase_actual = ""
            self.lbl_frase.configure(text="")
            self._frase_leida = True
            self.lbl_voz.configure(text="🎤 Esperando...", fg="#585b70")
            self._actualizar_profesor()

    def _guardar_en_historial(self, frase):
        hora = datetime.datetime.now().strftime("%H:%M")
        entrada = f"[{hora}] {frase}"
        self.historial.append(entrada)
        self.txt_historial.configure(state="normal")
        self.txt_historial.insert("end", f"• {entrada}\n")
        self.txt_historial.see("end")
        self.txt_historial.configure(state="disabled")
        self._actualizar_profesor()

    # ── Botones ───────────────────────────────────────────────────────────────

    def _leer_frase_manual(self):
        texto = (self.frase_actual + " " + self.palabra_actual).strip()
        if texto:
            self.tts.speak_phrase(texto)
            self.lbl_voz.configure(text=f"🔊 {texto}", fg=COLOR_ACENTO)
        else:
            self.lbl_estado.configure(text="No hay texto para leer.", fg=COLOR_WARN)

    def _borrar_letra(self):
        if self.palabra_actual:
            self.palabra_actual = self.palabra_actual[:-1]
            self.lbl_palabra.configure(text=self.palabra_actual)
        elif self.frase_actual:
            palabras = self.frase_actual.split()
            if palabras:
                self.palabra_actual = palabras[-1]
                self.frase_actual   = " ".join(palabras[:-1])
                self.lbl_palabra.configure(text=self.palabra_actual)
                self.lbl_frase.configure(text=self.frase_actual)
        self._actualizar_profesor()

    def _borrar_palabra(self):
        self.palabra_actual = ""
        self.lbl_palabra.configure(text="")
        self._actualizar_profesor()

    def _limpiar_todo(self):
        self.palabra_actual = ""
        self.frase_actual   = ""
        self._ultima_letra  = None
        self.lbl_palabra.configure(text="")
        self.lbl_frase.configure(text="")
        self.lbl_letra.configure(text="—")
        self.barra_confianza["value"] = 0
        self.lbl_voz.configure(text="🎤 Esperando...", fg="#585b70")
        self._actualizar_profesor()

    def _toggle_practica(self):
        self._modo_practica = self.var_practica.get()
        if self._modo_practica:
            self.lbl_estado.configure(
                text="🎯 Modo Práctica activo — las señas no se acumulan.",
                fg=COLOR_ACENTO)
        else:
            self.lbl_estado.configure(text="", fg=COLOR_FG)

    def _exportar_historial(self):
        if not self.historial:
            messagebox.showinfo("Historial vacío",
                                "No hay frases en el historial para exportar.")
            return
        fecha = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        ruta  = os.path.join(BASE_DIR, f"historial_{fecha}.txt")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("HISTORIAL DE SESIÓN — Traductor LSC\n")
            f.write(f"Fecha: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
            f.write("=" * 40 + "\n\n")
            for entrada in self.historial:
                f.write(f"• {entrada}\n")
        messagebox.showinfo("Exportado",
                            f"Historial guardado en:\n{ruta}")

    # ── Pantalla Profesor ─────────────────────────────────────────────────────

    def _abrir_pantalla_profesor(self):
        if self._ventana_profesor and self._ventana_profesor.winfo_exists():
            self._ventana_profesor.lift()
            return

        v = tk.Toplevel(self.root)
        v.title("Vista Profesor — LSC")
        v.configure(bg="#000000")
        v.geometry("800x500")
        self._ventana_profesor = v

        tk.Label(v, text="EL ESTUDIANTE DICE:",
                 bg="#000000", fg="#585b70",
                 font=("Segoe UI", 14)).pack(pady=(20, 0))

        self._prof_frase = tk.Label(v, text="",
                                    bg="#000000", fg="#ffffff",
                                    font=("Segoe UI", 52, "bold"),
                                    wraplength=760, justify="center")
        self._prof_frase.pack(expand=True)

        tk.Label(v, text="HISTORIAL",
                 bg="#000000", fg="#585b70",
                 font=("Segoe UI", 10)).pack()

        self._prof_historial = scrolledtext.ScrolledText(
            v, height=5, bg="#111111", fg="#a6e3a1",
            font=("Segoe UI", 13), state="disabled",
            relief="flat", padx=10, pady=6)
        self._prof_historial.pack(fill="x", padx=20, pady=(0, 20))

    def _actualizar_profesor(self):
        if not (self._ventana_profesor and self._ventana_profesor.winfo_exists()):
            return
        texto = (self.frase_actual + " " + self.palabra_actual).strip()
        self._prof_frase.configure(text=texto)

        self._prof_historial.configure(state="normal")
        self._prof_historial.delete("1.0", "end")
        for entrada in self.historial[-5:]:
            self._prof_historial.insert("end", f"• {entrada}\n")
        self._prof_historial.configure(state="disabled")

    # ── Entrenador ────────────────────────────────────────────────────────────

    def _abrir_entrenador(self):
        from gui.trainer import TrainerWindow
        ventana = tk.Toplevel(self.root)
        app = TrainerWindow(ventana)
        ventana.protocol("WM_DELETE_WINDOW", app.cerrar)
        ventana.bind("<Destroy>", lambda e: self.classifier.recargar())

    # ── Verificaciones ────────────────────────────────────────────────────────

    def _verificar_modelo(self):
        if not self.classifier.listo:
            msg = ("Modelo no encontrado. Use ⚙ Entrenador para capturar "
                   "señas y entrenar el sistema."
                   if self.classifier.error == MODEL_NOT_FOUND
                   else self.classifier.error)
            self.lbl_estado.configure(text=msg, fg=COLOR_WARN)

    # ── Cierre ────────────────────────────────────────────────────────────────

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
