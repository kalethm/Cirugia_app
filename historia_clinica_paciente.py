
import os
import json
import re
from datetime import date, datetime

import pandas as pd
import streamlit as st
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.lib import colors


CIRUGIA_COLUMNS = [
    "id",
    "nombre_paciente",
    "numero_documento",
    "institucion",
    "tipo_documento",
    "fecha_nacimiento",
    "sexo",
    "edad",
    "fecha_cirugia",
    "procedimiento",
    "checklist_iniciado",
    "preop_completa",
    "firmas_preop_completas",
    "intraop_completa",
    "postop_completa",
    "datos_preop",
    "datos_intraop",
    "datos_postop",
    "firma_aux_circulante",
    "firma_instrumentador",
    "firma_cirujano",
    "firma_anestesiologo",
    "pdf_checklist",
    "fecha_pdf_checklist",
]

BOOL_COLS = [
    "checklist_iniciado",
    "preop_completa",
    "firmas_preop_completas",
    "intraop_completa",
    "postop_completa",
]

HISTORIA_COLUMNS = [
    "id",
    "tipo_registro",
    "cirugia_id",
    "paciente",
    "fecha_registro",
    "fecha_cirugia",
    "procedimiento",
    "motivo",
    "diagnostico",
    "antecedentes",
    "observaciones",
    "pdf_checklist",
]


def bool_from_any(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "si", "sí", "yes"}


def normalize_document(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, int):
        return str(int(value))
    if isinstance(value, float):
        if float(value).is_integer():
            return str(int(value))
        text = f"{value}"
        return text.rstrip("0").rstrip(".")
    text = str(value).strip()
    if not text:
        return ""
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".")[0]
    return text


def from_json(text):
    if text is None:
        return {}
    if isinstance(text, dict):
        return text
    text = str(text).strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def ensure_dirs(data_dir: str = "data", assets_dir: str = "assets"):
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, "pdfs"), exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)


def get_paths(data_dir: str = "data", assets_dir: str = "assets"):
    ensure_dirs(data_dir, assets_dir)
    return {
        "cirugias": os.path.join(data_dir, "cirugias.csv"),
        "historia": os.path.join(data_dir, "historia_clinica.csv"),
        "pdfs_dir": os.path.join(data_dir, "pdfs"),
        "logo": os.path.join(assets_dir, "logo.png"),
    }


def load_cirugias(csv_path: str) -> pd.DataFrame:
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(columns=CIRUGIA_COLUMNS)

    for col in CIRUGIA_COLUMNS:
        if col not in df.columns:
            df[col] = False if col in BOOL_COLS else ""

    df = df[CIRUGIA_COLUMNS].copy()

    for col in BOOL_COLS:
        df[col] = df[col].apply(bool_from_any)

    df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
    if "numero_documento" in df.columns:
        df["numero_documento"] = df["numero_documento"].apply(normalize_document)
    return df


def load_historia(csv_path: str) -> pd.DataFrame:
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(columns=HISTORIA_COLUMNS)

    for col in HISTORIA_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[HISTORIA_COLUMNS].copy()
    df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
    df["cirugia_id"] = pd.to_numeric(df["cirugia_id"], errors="coerce").fillna(0).astype(int)
    if "paciente" in df.columns:
        df["paciente"] = df["paciente"].fillna("").astype(str).str.strip()
    return df


def save_historia(df: pd.DataFrame, csv_path: str):
    df.to_csv(csv_path, index=False)


def next_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1
    return int(df["id"].max()) + 1


def checklist_completo(row: pd.Series) -> bool:
    return (
        bool(row.get("preop_completa", False))
        and bool(row.get("firmas_preop_completas", False))
        and bool(row.get("intraop_completa", False))
        and bool(row.get("postop_completa", False))
    )


def draw_signature_pdf(c, x, y, title, image_path):
    width_img = 140
    height_img = 45

    if image_path and os.path.exists(str(image_path)):
        c.drawImage(
            ImageReader(str(image_path)),
            x,
            y,
            width=width_img,
            height=height_img,
            preserveAspectRatio=True,
            mask="auto",
        )

    c.line(x, y - 5, x + width_img, y - 5)
    c.setFont("Helvetica", 8)
    c.drawCentredString(x + width_img / 2, y - 16, title)


def card(c, x, y, w, h, title, bg_color=colors.HexColor("#F8FBFF"), header_color=colors.HexColor("#0B5ED7")):
    c.setFillColor(bg_color)
    c.roundRect(x, y, w, h, 10, stroke=0, fill=1)

    c.setFillColor(header_color)
    c.roundRect(x, y + h - 24, w, 24, 10, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 10, y + h - 16, title)
    c.setFillColor(colors.black)


def write_items(c, items, x, y, width, font_size=8, line_gap=11):
    c.setFont("Helvetica", font_size)
    current_y = y
    for label, value in items:
        text = f"{label}: {value}"
        lines = simpleSplit(text, "Helvetica", font_size, width)
        for line in lines:
            c.drawString(x, current_y, line)
            current_y -= line_gap
        current_y -= 2
    return current_y


def export_pdf(row: pd.Series, pdfs_dir: str, logo_path: str) -> str:
    pre = from_json(row.get("datos_preop", ""))
    intra = from_json(row.get("datos_intraop", ""))
    post = from_json(row.get("datos_postop", ""))

    file_name = f"checklist_cirugia_{int(row['id'])}.pdf"
    pdf_path = os.path.join(pdfs_dir, file_name)

    c = pdf_canvas.Canvas(pdf_path, pagesize=landscape(A4))
    page_width, page_height = landscape(A4)

    c.setFillColor(colors.HexColor("#EAF2FF"))
    c.rect(0, page_height - 84, page_width, 84, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#123B6D"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(30, page_height - 30, "Checklist de Cirugía Segura")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(30, page_height - 48, f"Paciente: {row.get('nombre_paciente', '')}")
    c.drawString(30, page_height - 62, f"Documento: {row.get('tipo_documento', '')} {row.get('numero_documento', '')}")
    c.drawString(250, page_height - 48, f"Edad: {row.get('edad', '')}")
    c.drawString(250, page_height - 62, f"Sexo: {row.get('sexo', '')}")
    c.drawString(430, page_height - 48, f"Fecha nacimiento: {row.get('fecha_nacimiento', '')}")
    c.drawString(430, page_height - 62, f"Institución: {row.get('institucion', '')}")
    c.drawString(30, page_height - 76, f"Fecha cirugía: {row.get('fecha_cirugia', '')}")
    c.drawString(250, page_height - 76, f"Procedimiento: {row.get('procedimiento', '')}")

    if os.path.exists(logo_path):
        c.drawImage(
            ImageReader(logo_path),
            page_width - 120,
            page_height - 70,
            width=80,
            height=50,
            preserveAspectRatio=True,
            mask="auto",
        )

    pre_items = [
        ("Identidad confirmada", "Sí" if pre.get("identificacion_confirmada") else "No"),
        ("Manilla de seguridad", "Sí" if pre.get("manilla_seguridad") else "No"),
        ("Sitio quirúrgico", pre.get("sitio_quirurgico", "")),
        ("Especificación", pre.get("sitio_especificado", "")),
        ("Procedimiento confirmado", "Sí" if pre.get("procedimiento_confirmado") else "No"),
        ("Consentimiento informado", "Sí" if pre.get("consentimiento_informado") else "No"),
        ("Historia clínica revisada", "Sí" if pre.get("historia_clinica_revisada") else "No"),
        ("Tiene alergias", pre.get("tiene_alergias", "")),
        ("Detalle alergias", pre.get("detalle_alergias", "")),
        ("Alergias verificadas", "Sí" if pre.get("alergias_verificadas") else "No"),
        ("Ayuno adecuado", "Sí" if pre.get("ayuno_adecuado") else "No"),
        ("Sitio preparado", "Sí" if pre.get("sitio_preparado") else "No"),
        ("Equipo utilizado", pre.get("equipo_utilizado", "")),
        ("Cantidad instrumentos", pre.get("cantidad_instrumentos", "")),
        ("Fecha esterilización", pre.get("fecha_esterilizacion", "")),
        ("Fecha vencimiento", pre.get("fecha_vencimiento", "")),
        ("Instrumental verificado", "Sí" if pre.get("instrumental_verificado") else "No"),
    ]

    intra_items = [
        ("Esterilidad del campo", "Sí" if intra.get("esterilidad_campo") else "No"),
        ("Gasas inicio", intra.get("gasas_inicio", "")),
        ("Gasas cierre", intra.get("gasas_cierre", "")),
        ("Compresas inicio", intra.get("compresas_inicio", "")),
        ("Compresas cierre", intra.get("compresas_cierre", "")),
        ("Conteo correcto", "Sí" if intra.get("conteo_correcto") else "No"),
        ("Posición paciente", intra.get("posicion_paciente", "")),
        ("Posición confirmada", "Sí" if intra.get("posicion_confirmada") else "No"),
        ("Medicamento tipo", intra.get("medicacion_tipo", "")),
        ("Dosis", intra.get("medicacion_dosis", "")),
        ("Medicación registrada", "Sí" if intra.get("medicacion_registrada") else "No"),
        ("Equipos funcionando", "Sí" if intra.get("equipos_funcionando") else "No"),
        ("Hora inicio", intra.get("hora_inicio", "")),
        ("Hora final", intra.get("hora_fin", "")),
        ("Tiempo registrado", "Sí" if intra.get("tiempo_registrado") else "No"),
        ("Hubo incidencias", intra.get("hubo_incidencias", "")),
        ("Detalle incidencias", intra.get("detalle_incidencias", "")),
        ("Incidencias registradas", "Sí" if intra.get("incidencias_registradas") else "No"),
    ]

    post_items = [
        ("Indicaciones postoperatorias", "Sí" if post.get("indicaciones_ok") else "No"),
        ("Comunicación con recuperación", "Sí" if post.get("comunicacion_recuperacion_ok") else "No"),
        ("Registro de medicamentos", "Sí" if post.get("registro_medicamentos_ok") else "No"),
        ("Drenajes y sondas", "Sí" if post.get("drenajes_ok") else "No"),
        ("Control del dolor", "Sí" if post.get("dolor_ok") else "No"),
        ("Control de conciencia", "Sí" if post.get("conciencia_ok") else "No"),
        ("Signos vitales", post.get("signos_vitales", "")),
        ("Signos confirmados", "Sí" if post.get("signos_ok") else "No"),
    ]

    x1, x2, x3 = 25, 285, 545
    y_card = 130
    card_w = 235
    card_h = 345

    card(c, x1, y_card, card_w, card_h, "Preoperatoria")
    card(c, x2, y_card, card_w, card_h, "Intraoperatoria")
    card(c, x3, y_card, card_w, card_h, "Postoperatoria")

    write_items(c, pre_items, x1 + 10, y_card + card_h - 38, card_w - 20)
    write_items(c, intra_items, x2 + 10, y_card + card_h - 38, card_w - 20)
    write_items(c, post_items, x3 + 10, y_card + card_h - 38, card_w - 20)

    c.setFillColor(colors.HexColor("#EEF4FB"))
    c.roundRect(25, 20, page_width - 50, 90, 10, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#123B6D"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(35, 95, "Firmas de confirmación")

    draw_signature_pdf(c, 35, 45, "Aux. enfermería circulante", row.get("firma_aux_circulante", ""))
    draw_signature_pdf(c, 225, 45, "Instrumentador/a QX", row.get("firma_instrumentador", ""))
    draw_signature_pdf(c, 415, 45, "Cirujano/a", row.get("firma_cirujano", ""))
    draw_signature_pdf(c, 605, 45, "Anestesiólogo/a", row.get("firma_anestesiologo", ""))

    c.save()
    return pdf_path


def normalize_datetime_string(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").fillna(pd.Timestamp("1900-01-01"))


def render_historia_clinica(data_dir: str = "data", assets_dir: str = "assets"):
    paths = get_paths(data_dir, assets_dir)
    cirugias = load_cirugias(paths["cirugias"])
    historia = load_historia(paths["historia"])

    if not cirugias.empty:
        cirugias = cirugias[cirugias["pdf_checklist"].fillna("").astype(str).str.strip() != ""].copy()

    st.title("🩺 Historia Clínica del Paciente")

    if cirugias.empty and historia.empty:
        st.warning("Todavía no hay pacientes ni cirugías archivadas.")
        return

    pacientes_base = []
    if not cirugias.empty:
        tmp = cirugias[["nombre_paciente", "numero_documento", "tipo_documento", "fecha_nacimiento", "sexo", "institucion"]].copy()
        tmp["nombre_paciente"] = tmp["nombre_paciente"].fillna("").astype(str).str.strip()
        tmp["numero_documento"] = tmp["numero_documento"].apply(normalize_document)
        pacientes_base.append(tmp)

    if pacientes_base:
        pacientes_df = pd.concat(pacientes_base, ignore_index=True).fillna("")
        pacientes_df = pacientes_df[pacientes_df["nombre_paciente"] != ""]
        pacientes_df = pacientes_df.drop_duplicates(subset=["nombre_paciente", "numero_documento"], keep="first")
        pacientes_df = pacientes_df.sort_values(by=["nombre_paciente", "numero_documento"])
    else:
        pacientes_df = pd.DataFrame(columns=["nombre_paciente", "numero_documento", "tipo_documento", "fecha_nacimiento", "sexo", "institucion"])

    st.subheader("🔎 Buscar paciente")
    filtro = st.text_input("Buscar por nombre o documento")
    if filtro.strip():
        patron = filtro.strip().lower()
        pacientes_filtrados = pacientes_df[
            pacientes_df["nombre_paciente"].astype(str).str.lower().str.contains(patron, na=False)
            | pacientes_df["numero_documento"].astype(str).str.lower().str.contains(patron, na=False)
        ].copy()
    else:
        pacientes_filtrados = pacientes_df.copy()

    if pacientes_filtrados.empty:
        st.warning("No se encontraron pacientes con ese criterio.")
        return

    opciones = pacientes_filtrados.apply(
        lambda r: f"{r['nombre_paciente']} | Doc: {r['numero_documento']}" if str(r["numero_documento"]).strip() else r["nombre_paciente"],
        axis=1,
    ).tolist()

    paciente_label = st.selectbox("Seleccione el paciente", opciones)
    paciente = paciente_label.split(" | Doc:")[0].strip()

    paciente_info = pacientes_filtrados[pacientes_filtrados["nombre_paciente"] == paciente].iloc[0]

    cirugias_paciente = cirugias[cirugias["nombre_paciente"] == paciente].copy()
    if not cirugias_paciente.empty:
        cirugias_paciente["_fecha_sort"] = normalize_datetime_string(cirugias_paciente["fecha_cirugia"])
        cirugias_paciente = cirugias_paciente.sort_values(by=["_fecha_sort", "id"], ascending=[False, False]).drop(columns=["_fecha_sort"])

    historia_paciente = historia[historia["paciente"] == paciente].copy()
    if not historia_paciente.empty:
        historia_paciente["_fecha_sort"] = normalize_datetime_string(historia_paciente["fecha_registro"])
        historia_paciente = historia_paciente.sort_values(by=["_fecha_sort", "id"], ascending=[False, False]).drop(columns=["_fecha_sort"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cirugías archivadas", len(cirugias_paciente))
    c2.metric("Registros clínicos", len(historia_paciente))
    c3.metric("Checklists con PDF", int((cirugias_paciente["pdf_checklist"].fillna("").astype(str).str.strip() != "").sum()) if not cirugias_paciente.empty else 0)
    c4.metric("Checklists completos", int(cirugias_paciente.apply(checklist_completo, axis=1).sum()) if not cirugias_paciente.empty else 0)

    st.divider()
    st.subheader("👤 Datos del paciente")
    d1, d2, d3, d4 = st.columns(4)
    d1.write(f"**Nombre:** {paciente_info.get('nombre_paciente', '')}")
    d2.write(f"**Documento:** {paciente_info.get('numero_documento', '')}")
    d3.write(f"**Sexo:** {paciente_info.get('sexo', '')}")
    d4.write(f"**Fecha de nacimiento:** {paciente_info.get('fecha_nacimiento', '')}")
    st.caption(f"Institución: {paciente_info.get('institucion', '')}")

    st.divider()
    st.subheader("🕘 Registros más recientes del paciente")
    recientes = []

    if not historia_paciente.empty:
        for _, r in historia_paciente.iterrows():
            recientes.append({
                "Fecha": r.get("fecha_registro", ""),
                "Tipo": r.get("tipo_registro", "Evolución clínica") or "Evolución clínica",
                "Cirugía": int(r.get("cirugia_id", 0)),
                "Procedimiento": r.get("procedimiento", ""),
                "Motivo": r.get("motivo", ""),
                "PDF": "Sí" if str(r.get("pdf_checklist", "")).strip() else "No",
            })

    if not cirugias_paciente.empty:
        # Añadir cirugías con PDF si todavía no están en historia
        historia_ids_pdf = set(
            historia_paciente.loc[
                historia_paciente["tipo_registro"].astype(str) == "Checklist cirugía segura", "cirugia_id"
            ].astype(int).tolist()
        ) if not historia_paciente.empty else set()

        extras = cirugias_paciente[
            (cirugias_paciente["pdf_checklist"].fillna("").astype(str).str.strip() != "")
            & (~cirugias_paciente["id"].isin(historia_ids_pdf))
        ].copy()

        for _, r in extras.iterrows():
            recientes.append({
                "Fecha": r.get("fecha_pdf_checklist", "") or r.get("fecha_cirugia", ""),
                "Tipo": "Checklist cirugía segura",
                "Cirugía": int(r.get("id", 0)),
                "Procedimiento": r.get("procedimiento", ""),
                "Motivo": "Checklist quirúrgico generado",
                "PDF": "Sí",
            })

    if recientes:
        tabla_recientes = pd.DataFrame(recientes)
        tabla_recientes["_sort"] = normalize_datetime_string(tabla_recientes["Fecha"])
        tabla_recientes = tabla_recientes.sort_values(by="_sort", ascending=False).drop(columns=["_sort"])
        st.dataframe(tabla_recientes, use_container_width=True, hide_index=True)
    else:
        st.info("Este paciente todavía no tiene registros recientes.")

    st.divider()
    st.subheader("📌 Cirugías archivadas del paciente")

    if cirugias_paciente.empty:
        st.info("Este paciente no tiene cirugías archivadas.")
    else:
        tabla_cirugias = cirugias_paciente[[
            "id",
            "fecha_cirugia",
            "procedimiento",
            "institucion",
            "sexo",
            "fecha_nacimiento",
            "preop_completa",
            "firmas_preop_completas",
            "intraop_completa",
            "postop_completa",
            "fecha_pdf_checklist",
        ]].copy()
        tabla_cirugias.columns = [
            "ID cirugía",
            "Fecha cirugía",
            "Procedimiento",
            "Institución",
            "Sexo",
            "Fecha nacimiento",
            "Preop",
            "Firmas",
            "Intraop",
            "Postop",
            "Fecha PDF",
        ]
        st.dataframe(tabla_cirugias, use_container_width=True, hide_index=True)

        st.markdown("### 📥 Descargar checklist por cirugía")
        for _, row in cirugias_paciente.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([4, 2, 2])
                with col1:
                    st.markdown(
                        f"**Cirugía #{int(row['id'])}**  \nFecha: {row.get('fecha_cirugia', '')}  \nProcedimiento: {row.get('procedimiento', '')}"
                    )
                with col2:
                    pdf_existente = str(row.get("pdf_checklist", "")).strip()
                    st.write("PDF archivado" if pdf_existente else "Sin PDF archivado")
                with col3:
                    pdf_path = str(row.get("pdf_checklist", "")).strip()
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as file_pdf:
                            st.download_button(
                                label=f"Descargar PDF #{int(row['id'])}",
                                data=file_pdf,
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf",
                                key=f"descarga_pdf_cx_{int(row['id'])}",
                            )
                    elif checklist_completo(row):
                        nuevo_pdf = export_pdf(row, paths["pdfs_dir"], paths["logo"])
                        with open(nuevo_pdf, "rb") as file_pdf:
                            st.download_button(
                                label=f"Generar y descargar PDF #{int(row['id'])}",
                                data=file_pdf,
                                file_name=os.path.basename(nuevo_pdf),
                                mime="application/pdf",
                                key=f"regen_pdf_cx_{int(row['id'])}",
                            )
                    else:
                        st.caption("Checklist incompleto")

    st.divider()
    st.subheader("📋 Historial clínico del paciente")

    if historia_paciente.empty:
        st.info("Este paciente aún no tiene evolución clínica registrada.")
    else:
        tabla_historia = historia_paciente[[
            "fecha_registro",
            "tipo_registro",
            "cirugia_id",
            "fecha_cirugia",
            "procedimiento",
            "motivo",
            "diagnostico",
            "antecedentes",
            "observaciones",
        ]].copy()

        tabla_historia.columns = [
            "Fecha registro",
            "Tipo de registro",
            "ID cirugía",
            "Fecha cirugía",
            "Procedimiento",
            "Motivo",
            "Diagnóstico",
            "Antecedentes",
            "Observaciones",
        ]
        st.dataframe(tabla_historia, use_container_width=True, hide_index=True)

        st.markdown("### 📎 Descargas desde el historial")
        registros_pdf = historia_paciente[historia_paciente["pdf_checklist"].fillna("").astype(str).str.strip() != ""].copy()
        if registros_pdf.empty:
            st.caption("No hay PDFs archivados en los registros de historial de este paciente.")
        else:
            for _, reg in registros_pdf.iterrows():
                pdf_path = str(reg.get("pdf_checklist", "")).strip()
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label=f"Descargar {reg.get('tipo_registro', 'PDF')} | Cirugía #{int(reg.get('cirugia_id', 0))}",
                            data=f,
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf",
                            key=f"descarga_hist_{int(reg.get('id', 0))}",
                        )

    st.divider()
    st.subheader("➕ Nueva evolución clínica")

    if cirugias_paciente.empty:
        st.warning("No es posible registrar una evolución clínica porque el paciente no tiene cirugías archivadas.")
        return

    opciones_cirugia = cirugias_paciente["id"].tolist()

    with st.form("form_historia_clinica"):
        cirugia_id = st.selectbox(
            "Asociar a cirugía archivada",
            options=opciones_cirugia,
            format_func=lambda x: f"Cirugía #{int(x)} | {cirugias_paciente.loc[cirugias_paciente['id'] == x, 'fecha_cirugia'].iloc[0]} | {cirugias_paciente.loc[cirugias_paciente['id'] == x, 'procedimiento'].iloc[0]}",
        )

        fila_cx = cirugias_paciente[cirugias_paciente["id"] == int(cirugia_id)].iloc[0]

        motivo = st.text_input("Motivo de consulta")
        diagnostico = st.text_input("Diagnóstico")
        antecedentes = st.text_area("Antecedentes")
        observaciones = st.text_area("Observaciones")
        guardar = st.form_submit_button("Guardar evolución clínica")

        if guardar:
            errores = []
            if not motivo.strip():
                errores.append("El motivo de consulta es obligatorio.")
            if not diagnostico.strip():
                errores.append("El diagnóstico es obligatorio.")

            if errores:
                for err in errores:
                    st.error(err)
            else:
                nueva_fila = pd.DataFrame([{
                    "id": next_id(historia),
                    "tipo_registro": "Evolución clínica",
                    "cirugia_id": int(cirugia_id),
                    "paciente": paciente,
                    "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "fecha_cirugia": str(fila_cx.get("fecha_cirugia", "")),
                    "procedimiento": str(fila_cx.get("procedimiento", "")),
                    "motivo": motivo.strip(),
                    "diagnostico": diagnostico.strip(),
                    "antecedentes": antecedentes.strip(),
                    "observaciones": observaciones.strip(),
                    "pdf_checklist": "",
                }])

                historia = pd.concat([historia, nueva_fila], ignore_index=True)
                save_historia(historia, paths["historia"])
                st.success("Historia clínica actualizada y ligada a la cirugía seleccionada.")
                st.rerun()


if __name__ == "__main__":
    render_historia_clinica()
