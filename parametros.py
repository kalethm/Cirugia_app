"""Catálogos parametrizables del sistema (solo administrador).

Permite añadir, activar/desactivar y eliminar valores (instituciones,
cirujanos, procedimientos, etc.) que alimentan formularos y filtros.
Persistencia en data/parametros.csv.
"""
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from navegacion import botones_nav

COLUMNAS = ["categoria", "valor", "activo", "modificado", "usuario"]

CATEGORIAS = {
    "Pacientes": ["tipo_documento", "sexo", "institucion"],
    "Cirugía": ["procedimiento", "cirujano", "quirofano"],
    "Historia clínica": ["motivo_consulta"],
    "Esterilización": ["categoria_insumo", "metodo", "empaque", "especialidad"],
}

DESCRIPCIONES = {
    "tipo_documento": "Documentos de identidad aceptados en el ingreso de pacientes.",
    "sexo": "Opciones de sexo registradas en la ficha del paciente.",
    "institucion": "EPS e instituciones que aparecen en filtros y métricas.",
    "procedimiento": "Procedimientos quirúrgicos frecuentes (sugeridos en el ingreso).",
    "cirujano": "Cirujanos del servicio; alimentan el filtro por doctor en Métricas.",
    "motivo_consulta": "Motivos de consulta de historia clínica.",
    "categoria_insumo": "Categorías de insumos de la central de esterilización.",
    "metodo": "Métodos de esterilización disponibles.",
    "empaque": "Tipos de empaque usados para calcular la vigencia de los sets.",
    "especialidad": "Especialidades quirúrgicas del inventario.",
}

SEMILLA = {
    "tipo_documento": ["C.C", "C.E", "T.I", "PPT", "Otro"],
    "sexo": ["Masculino", "Femenino", "Otro"],
    "institucion": ["Sura", "Nueva EPS", "Sanitas", "Compensar", "Particular"],
    "procedimiento": [],
    "cirujano": [],
    "quirofano": ["Quirófano 1", "Quirófano 2", "Quirófano 3"],
    "motivo_consulta": [],
    "categoria_insumo": ["Indicador químico", "Indicador biológico", "Empaque", "Detergente", "Solución", "Otro"],
    "metodo": ["Autoclave vapor", "Óxido de etileno", "Peróxido de hidrógeno", "Plasma"],
    "empaque": ["Textil doble", "SMS", "Papel crepado", "Bolsa mixta", "Contenedor rígido", "Tyvek"],
    "especialidad": ["General", "Ortopedia", "Ginecología", "Neurocirugía", "Cardiología", "Otra"],
}


def ruta(data_dir="data"):
    return os.path.join(data_dir, "parametros.csv")


def cargar(data_dir="data"):
    path = ruta(data_dir)
    if not os.path.exists(path):
        filas = [{"categoria": c, "valor": v, "activo": True, "modificado": "", "usuario": "Sistema"}
                 for c, vs in SEMILLA.items() for v in vs]
        df = pd.DataFrame(filas, columns=COLUMNAS)
        df.to_csv(path, index=False)
        return df
    df = pd.read_csv(path, dtype=str).fillna("")
    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = ""
    df["activo"] = df["activo"].astype(str).str.lower().isin(["true", "1", "si", "sí"])
    faltantes = [c for c in SEMILLA if not (df["categoria"] == c).any()]
    if faltantes:
        extra = pd.DataFrame([{"categoria": c, "valor": v, "activo": True, "modificado": "", "usuario": "Sistema"}
                              for c in faltantes for v in SEMILLA[c]], columns=COLUMNAS)
        df = pd.concat([df, extra], ignore_index=True)
        df.to_csv(path, index=False)
    return df[COLUMNAS].copy()


def guardar(df, data_dir="data"):
    df[COLUMNAS].to_csv(ruta(data_dir), index=False)


def opciones(categoria, data_dir="data"):
    df = cargar(data_dir)
    if df.empty:
        return []
    vals = df[(df["categoria"] == categoria) & df["activo"]]["valor"].astype(str).str.strip()
    return sorted(v for v in vals.unique() if v)


def _usuario():
    return str(st.session_state.get("usuario", "Sistema"))


def _ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _guardar_cambio(df, mascara, activo, data_dir):
    df.loc[mascara, "activo"] = activo
    df.loc[mascara, "modificado"] = _ahora()
    df.loc[mascara, "usuario"] = _usuario()
    guardar(df, data_dir)


def _tarjeta_categoria(df, cat, data_dir):
    """Una tarjeta por categoría con sus valores y acciones."""
    bloque = df[df["categoria"] == cat].sort_values("valor")
    activos = bloque[bloque["activo"]]
    inactivos = bloque[~bloque["activo"]]
    n_act = len(activos)
    n_inact = len(inactivos)

    with st.container(border=True):
        col_t, col_n = st.columns([4, 1])
        with col_t:
            st.markdown(f"**{cat}**")
            if DESCRIPCIONES.get(cat):
                st.caption(DESCRIPCIONES[cat])
        with col_n:
            st.metric("Activos", n_act, delta=f"{n_inact} inactivos" if n_inact else None)

        if bloque.empty:
            st.caption("Sin valores todavía. Agrega el primero abajo.")
        else:
            chips = "  ".join(
                f"`{v}`" if a else f"~~`{v}`~~"
                for v, a in zip(bloque["valor"], bloque["activo"])
            )
            st.markdown(chips)

        a1, a2, a3 = st.columns([2, 2, 3])
        with a1:
            with st.form(f"alta_{cat}", clear_on_submit=True):
                nuevo = st.text_input("Agregar valor", key=f"nuevo_{cat}", label_visibility="collapsed", placeholder="Nuevo valor…")
                if st.form_submit_button("➕ Agregar", width="stretch") and nuevo.strip():
                    v = nuevo.strip()
                    existe = ((df["categoria"] == cat) & (df["valor"].astype(str).str.strip() == v)).any()
                    if existe:
                        st.warning("Ya existe.")
                    else:
                        df_nuevo = pd.concat([df, pd.DataFrame([[cat, v, True, _ahora(), _usuario()]], columns=COLUMNAS)], ignore_index=True)
                        guardar(df_nuevo, data_dir)
                        st.rerun()
        with a2:
            sel = st.multiselect("Desactivar", sorted(activos["valor"].astype(str).tolist()), key=f"des_{cat}", label_visibility="collapsed", placeholder="Desactivar…")
            if st.button("🚫 Desactivar", key=f"btn_des_{cat}", disabled=not sel, width="stretch"):
                _guardar_cambio(df, (df["categoria"] == cat) & (df["valor"].astype(str).isin(sel)), False, data_dir)
                st.rerun()
        with a3:
            sel_act = st.multiselect("Activar", sorted(inactivos["valor"].astype(str).tolist()), key=f"act_{cat}", label_visibility="collapsed", placeholder="Activar inactivos…")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Activar", key=f"btn_act_{cat}", disabled=not sel_act, width="stretch"):
                    _guardar_cambio(df, (df["categoria"] == cat) & (df["valor"].astype(str).isin(sel_act)), True, data_dir)
                    st.rerun()
            with c2:
                sel_del = st.multiselect("Eliminar", sorted(bloque["valor"].astype(str).tolist()), key=f"del_{cat}", label_visibility="collapsed", placeholder="Eliminar…")
                if st.button("🗑️", key=f"btn_del_{cat}", disabled=not sel_del, width="stretch"):
                    mascara = (df["categoria"] == cat) & (df["valor"].astype(str).isin(sel_del))
                    guardar(df[~mascara], data_dir)
                    st.rerun()


def render_parametros(data_dir="data", sidebar=None):
    st.title("🗄️ Base de datos y parámetros")
    st.caption("Catálogos de valores usados en los formularios y filtros de toda la aplicación. Los valores tachados están inactivos: no aparecen en los formularios pero conservan el historial.")
    if st.session_state.get("rol") != "Administrador":
        st.error("Solo el administrador puede gestionar los parámetros.")
        return

    df = cargar(data_dir)
    total = len(df)
    activos_total = int(df["activo"].sum()) if not df.empty else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("Categorías", len(CATEGORIAS))
    m2.metric("Valores activos", activos_total)
    m3.metric("Valores inactivos", total - activos_total)

    grupos = list(CATEGORIAS)
    panel = botones_nav(grupos, "panel_parametros", contenedor=sidebar or st.sidebar, titulo="Parámetros")
    st.subheader(panel)
    for cat in CATEGORIAS[panel]:
        _tarjeta_categoria(df, cat, data_dir)
