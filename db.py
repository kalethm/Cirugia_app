"""Persistencia SQLite para la app (data/app.db).

Cada conjunto de datos se guarda como una tabla SQLite. En la primera
lectura, si la tabla no existe pero hay un CSV legado, se importa
automáticamente. Cada guardado crea además un respaldo diario en
data/backups/ (respaldo automático).
"""
import os
import shutil
import sqlite3
from datetime import date, datetime

import pandas as pd

RUTA_DB = os.path.join("data", "app.db")
DIR_BACKUP = os.path.join("data", "backups")

_ARCHIVOS = {
    "usuarios": "data/usuarios.csv",
    "pacientes": "data/pacientes.csv",
    "cirugias": "data/cirugias.csv",
    "historia_clinica": "data/historia_clinica.csv",
    "parametros": "data/parametros.csv",
    "programacion": "data/programacion.csv",
    "est_cargas": "data/esterilizacion/cargas.csv",
    "est_despachos": "data/esterilizacion/despachos.csv",
    "est_equipos": "data/esterilizacion/equipos.csv",
    "est_instrumental": "data/esterilizacion/instrumental.csv",
    "est_insumos": "data/esterilizacion/insumos.csv",
    "est_movimientos_insumos": "data/esterilizacion/movimientos_insumos.csv",
    "est_proveedores": "data/esterilizacion/proveedores.csv",
}


def _conn():
    return sqlite3.connect(RUTA_DB)


def leer(nombre: str) -> pd.DataFrame:
    """Lee una tabla; si no existe, la importa desde su CSV legado."""
    if os.path.exists(RUTA_DB):
        try:
            with _conn() as c:
                return pd.read_sql(f'SELECT * FROM "{nombre}"', c)
        except Exception:
            pass
    csv = _ARCHIVOS.get(nombre)
    if csv and os.path.exists(csv):
        df = pd.read_csv(csv, dtype=str).fillna("")
        guardar(nombre, df)
        return df
    return pd.DataFrame()


def guardar(nombre: str, df: pd.DataFrame):
    os.makedirs("data", exist_ok=True)
    with _conn() as c:
        df.to_sql(nombre, c, if_exists="replace", index=False)
    _snapshot()


def _snapshot():
    """Respaldo automático: una copia de app.db por día."""
    if not os.path.exists(RUTA_DB):
        return
    dest = os.path.join(DIR_BACKUP, f"app_{date.today():%Y-%m-%d}.db")
    if not os.path.exists(dest):
        os.makedirs(DIR_BACKUP, exist_ok=True)
        shutil.copy2(RUTA_DB, dest)


def crear_respaldo() -> str:
    os.makedirs(DIR_BACKUP, exist_ok=True)
    dest = os.path.join(DIR_BACKUP, f"app_{datetime.now():%Y-%m-%d_%H%M%S}.db")
    shutil.copy2(RUTA_DB, dest)
    return dest


def restaurar(origen: str):
    os.makedirs("data", exist_ok=True)
    shutil.copy2(origen, RUTA_DB)


def tablas() -> list:
    if not os.path.exists(RUTA_DB):
        return []
    with _conn() as c:
        return [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]


def resumen() -> dict:
    out = {}
    for t in tablas():
        try:
            with _conn() as c:
                out[t] = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except Exception:
            out[t] = "?"
    return out
