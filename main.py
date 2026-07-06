"""
main.py
Punto de entrada del Traductor LSC.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import abrir_app

if __name__ == "__main__":
    abrir_app()
