"""
train.py
Entrena un RandomForestClassifier con data/dataset.csv y guarda el modelo en models/lsc_model.pkl.
Puede ejecutarse desde CLI o ser llamado por el Modo Entrenador.
"""

import os
import sys
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(BASE_DIR, "data", "dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "lsc_model.pkl")


def entrenar():
    # 1. Cargar dataset
    if not os.path.exists(DATA_PATH):
        msg = "Error: No se encontró data/dataset.csv. Capture señas primero."
        print(msg)
        return msg

    df = pd.read_csv(DATA_PATH)
    if len(df) < 20:
        msg = "Error: El dataset tiene muy pocas muestras. Capture más señas."
        print(msg)
        return msg

    conteo = df["letra"].value_counts()
    clases_validas = conteo[conteo >= 2].index
    df = df[df["letra"].isin(clases_validas)]

    X = df.drop(columns=["letra"]).values
    y = df["letra"].values

    # 2. Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    # 3. Entrenar
    modelo = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    modelo.fit(X_train, y_train)

    # 4. Evaluar
    y_pred = modelo.predict(X_test)
    precision = accuracy_score(y_test, y_pred) * 100
    reporte = classification_report(y_test, y_pred, zero_division=0)
    print(reporte)

    # 5. Guardar
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(modelo, MODEL_PATH)

    msg = f"¡Modelo entrenado exitosamente! Precisión en validación: {precision:.1f}%"
    print(msg)
    return msg


if __name__ == "__main__":
    entrenar()
