from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import os

import os
import json
import uuid
import numpy as np
import pandas as pd
import streamlit as st

from datetime import date, datetime, timedelta
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.utils import ImageReader, simpleSplit

from auth import login
from cirugia import render_cirugia

# =========================
# CONFIG
# =========================
RUTA_CIRUGIAS = "data/cirugias.csv"
RUTA_FIRMAS = "data/firmas"
RUTA_PDFS = "data/pdfs"
RUTA_LOGO = "assets/logo.png"

os.makedirs("data", exist_ok=True)
os.makedirs(RUTA_FIRMAS, exist_ok=True)
os.makedirs(RUTA_PDFS, exist_ok=True)



# =========================
# CONFIGURACIÓN
# =========================
st.set_page_config(
    page_title="Gestión de Cirugías",
    layout="wide"
)

# =========================
# SESIÓN
# =========================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    login()
    st.stop()

# =========================
# FUNCIONES
# =========================
def cargar_csv(ruta, columnas):
    try:
        return pd.read_csv(ruta)
    except:
        return pd.DataFrame(columns=columnas)

# =========================
# DATOS
# =========================
pacientes = cargar_csv(
    "data/pacientes.csv",
    ["id", "nombre", "documento", "edad", "sexo"]
)

cirugias = cargar_csv(
    "data/cirugias.csv",
    ["id", "paciente", "procedimiento", "fecha", "cirujano"]
)

checklist = cargar_csv(
    "data/checklist.csv",
    ["paciente", "fecha", "fase", "item", "estado"]
)

# =========================
# SIDEBAR
# =========================
st.sidebar.success(
    f"👤 {st.session_state['usuario']} | {st.session_state['rol']}"
)

if st.sidebar.button("Cerrar sesión"):
    st.session_state.clear()
    st.rerun()

menu = st.sidebar.radio(
    "Menú",
    [
        "Inicio",
        "Historial de Pacientes",
        "Cirugía",
        "Historia Clínica del Paciente"
    ]
)

# =========================
# PANTALLAS
# =========================
if menu == "Inicio":
    st.title("🏥 Sistema de Gestión de Cirugías")
    st.info("Sistema clínico para control de pacientes, cirugías y checklist OMS.")

# =========================
elif menu == "Cirugía":
   render_cirugia()


# =========================
elif menu == "Historial de Pacientes":
    st.title("📋 Historial de Pacientes")
    st.dataframe(pacientes, use_container_width=True)


#==================================
elif menu == "Historia Clínica del Paciente":
    st.title("🩺 Historia Clínica")

    historia = cargar_csv(
        "data/historia_clinica.csv",
        ["paciente", "fecha", "motivo", "diagnostico", "antecedentes", "observaciones"]
    )

    paciente = st.selectbox("Seleccione el paciente", pacientes["nombre"])

    st.subheader("📋 Historial clínico")
    st.dataframe(
        historia[historia["paciente"] == paciente],
        use_container_width=True
    )

    st.subheader("➕ Nueva evolución clínica")
    with st.form("form_historia"):
        motivo = st.text_input("Motivo de consulta")
        diagnostico = st.text_input("Diagnóstico")
        antecedentes = st.text_area("Antecedentes")
        observaciones = st.text_area("Observaciones")
        guardar = st.form_submit_button("Guardar")

        if guardar:
            historia.loc[len(historia)] = [
                paciente,
                date.today(),
                motivo,
                diagnostico,
                antecedentes,
                observaciones
            ]
            historia.to_csv("data/historia_clinica.csv", index=False)
            st.success("Historia clínica actualizada")

