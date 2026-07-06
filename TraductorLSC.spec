# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Recopilar archivos de datos de mediapipe (modelos .tflite, etc.)
mediapipe_datas = collect_data_files('mediapipe')

# Carpetas del proyecto (solo si existen al empaquetar)
project_datas = []
if os.path.exists('data/dataset.csv'):
    project_datas.append(('data', 'data'))
if os.path.exists('models/lsc_model.pkl'):
    project_datas.append(('models', 'models'))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=collect_dynamic_libs('mediapipe'),
    datas=mediapipe_datas + project_datas,
    hiddenimports=[
        'sklearn.ensemble._forest',
        'sklearn.tree._classes',
        'sklearn.utils._bunch',
        'joblib',
        'mediapipe',
        'cv2',
        'PIL',
        'pyttsx3',
        'pyttsx3.drivers',
        'pyttsx3.drivers.sapi5',
        'win32com.client',
        'comtypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'IPython', 'notebook'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TraductorLSC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # Sin ventana de consola negra
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
