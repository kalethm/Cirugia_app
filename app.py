from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import os



import streamlit as st
import pandas as pd
from datetime import date
from auth import login


#====================================
#FUNCIONES EXTERNAS
def exportar_checklist_pdf(paciente, df):
    os.makedirs("pdfs", exist_ok=True)

    archivo = f"pdfs/Checklist_OMS_{paciente.replace(' ', '_')}.pdf"
    doc = SimpleDocTemplate(archivo, pagesize=A4)

    styles = getSampleStyleSheet()
    elementos = []

    # Título
    elementos.append(Paragraph(
        "<b>LISTA DE VERIFICACIÓN DE LA SEGURIDAD DE LA CIRUGÍA (OMS)</b>",
        styles["Title"]
    ))
    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph(f"<b>Paciente:</b> {paciente}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Fecha:</b> {df['fecha'].iloc[0]}", styles["Normal"]))
    elementos.append(Spacer(1, 12))

    for fase in df["fase"].unique():
        elementos.append(Paragraph(f"<b>{fase}</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 6))

        data = [["Ítem", "Cumple"]]

        for _, row in df[df["fase"] == fase].iterrows():
            estado = "✔" if row["estado"] else "✘"
            data.append([row["item"], estado])

        tabla = Table(data, colWidths=[400, 80])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (1, 1), (-1, -1), "CENTER")
        ]))

        elementos.append(tabla)
        elementos.append(Spacer(1, 12))

    doc.build(elementos)
    return archivo


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
        "Ingreso de Paciente",
        "Historial de Pacientes",
        "Ingreso de Cirugía",
        "Checklist Cirugía Segura",
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
elif menu == "Ingreso de Paciente":
    if st.session_state["rol"] not in ["Administrador", "Enfermeria"]:
        st.error("No tiene permisos para este módulo")
        st.stop()

    st.title("👤 Ingreso de Paciente")

    with st.form("form_paciente"):
        nombre = st.text_input("Nombre completo")
        documento = st.text_input("Documento")
        edad = st.number_input("Edad", 0, 120)
        sexo = st.selectbox("Sexo", ["Masculino", "Femenino", "Otro"])
        guardar = st.form_submit_button("Guardar")

        if guardar:
            pacientes.loc[len(pacientes)] = [
                len(pacientes) + 1,
                nombre,
                documento,
                edad,
                sexo
            ]
            pacientes.to_csv("data/pacientes.csv", index=False)
            st.success("Paciente registrado correctamente")

# =========================
elif menu == "Historial de Pacientes":
    st.title("📋 Historial de Pacientes")
    st.dataframe(pacientes, use_container_width=True)

# =========================
elif menu == "Ingreso de Cirugía":
    if st.session_state["rol"] != "Cirujano":
        st.warning("Solo el cirujano puede registrar cirugías")
        st.stop()

    st.title("🏥 Ingreso de Cirugía")

    paciente = st.selectbox("Paciente", pacientes["nombre"])

    with st.form("form_cirugia"):
        procedimiento = st.text_input("Procedimiento")
        fecha = st.date_input("Fecha", date.today())
        cirujano = st.text_input("Cirujano")
        guardar = st.form_submit_button("Guardar")

        if guardar:
            cirugias.loc[len(cirugias)] = [
                len(cirugias) + 1,
                paciente,
                procedimiento,
                fecha,
                cirujano
            ]
            cirugias.to_csv("data/cirugias.csv", index=False)
            st.success("Cirugía registrada")

# =========================
elif menu == "Checklist Cirugía Segura":
    st.title("✅ Lista de Verificación de la Seguridad de la Cirugía (OMS)")

    paciente = st.selectbox("Paciente", pacientes["nombre"])
    fecha = date.today()

    fase = st.radio(
        "Fase",
        [
            "Entrada (Antes de la anestesia)",
            "Pausa quirúrgica (Antes de la incisión)",
            "Salida (Antes de salir del quirófano)"
        ]
    )

    checklist_oms = {
        "Entrada (Antes de la anestesia)": [
            "Identidad confirmada",
            "Sitio quirúrgico confirmado",
            "Procedimiento confirmado",
            "Consentimiento informado",
            "Sitio quirúrgico demarcado (si procede)",
            "Control de seguridad de anestesia completado",
            "Pulsioxímetro colocado y funcionando",
            "Alergias conocidas verificadas",
            "Vía aérea difícil / riesgo de aspiración evaluado",
            "Riesgo de hemorragia mayor a 500 ml evaluado"
        ],
        "Pausa quirúrgica (Antes de la incisión)": [
            "Equipo se presenta por nombre y función",
            "Identidad del paciente confirmada verbalmente",
            "Sitio quirúrgico confirmado verbalmente",
            "Procedimiento confirmado verbalmente",
            "Cirujano revisa pasos críticos y duración",
            "Anestesia revisa problemas específicos del paciente",
            "Enfermería confirma esterilidad del instrumental",
            "Profilaxis antibiótica administrada en últimos 60 minutos",
            "Imágenes diagnósticas esenciales disponibles"
        ],
        "Salida (Antes de salir del quirófano)": [
            "Nombre del procedimiento realizado",
            "Recuento de instrumental correcto",
            "Recuento de gasas correcto",
            "Recuento de agujas correcto",
            "Muestras correctamente etiquetadas",
            "Problemas con instrumental o equipos registrados",
            "Indicaciones de recuperación y tratamiento revisadas"
        ]
    }

    estados = {}
    for item in checklist_oms[fase]:
        estados[item] = st.checkbox(item)

    if st.button("Guardar Checklist OMS"):
        for item, estado in estados.items():
            checklist.loc[len(checklist)] = [
                paciente,
                fecha,
                fase,
                item,
                estado
            ]
        checklist.to_csv("data/checklist.csv", index=False)
        st.success("Checklist OMS guardado correctamente")

    st.divider()
    st.subheader("📄 Exportar Checklist")

    if st.button("Exportar Checklist OMS a PDF"):
        datos_paciente = checklist[checklist["paciente"] == paciente]

        if datos_paciente.empty:
            st.warning("No hay checklist registrado para este paciente")
        else:
            archivo_pdf = exportar_checklist_pdf(paciente, datos_paciente)
            st.success("PDF generado correctamente")

            with open(archivo_pdf, "rb") as f:
                st.download_button(
                label="📥 Descargar PDF",
                data=f,
                file_name=archivo_pdf.split("/")[-1],
                mime="application/pdf"
            )


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

