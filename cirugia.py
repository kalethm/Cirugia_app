import os
import json
import uuid
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

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
]

BOOL_COLS = [
    "checklist_iniciado",
    "preop_completa",
    "firmas_preop_completas",
    "intraop_completa",
    "postop_completa",
]

TIPOS_DOCUMENTO = ["R.C", "T.I", "C.C", "OTRO"]
SITIOS_QUIRURGICOS = [
    "",
    "Cabeza y cuello",
    "Tórax",
    "Abdomen",
    "Espalda / columna",
    "Pelvis / periné",
    "Miembro superior derecho",
    "Miembro superior izquierdo",
    "Miembro inferior derecho",
    "Miembro inferior izquierdo",
    "Especifique",
]
POSICIONES_PACIENTE = [
    "",
    "Decúbito supino",
    "Decúbito prono",
    "Decúbito lateral derecho",
    "Decúbito lateral izquierdo",
    "Litotomía",
    "Trendelenburg",
    "Trendelenburg invertida",
    "Fowler",
    "Semi-Fowler",
    "Sims",
    "Genupectoral",
    "Sentada",
    "Navaja sevillana",
    "Posición renal",
    "Ortopédica con tracción",
]


def bool_from_any(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "si", "sí", "yes"}


def to_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


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


def ensure_dirs(data_dir: str, assets_dir: str):
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, "firmas"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "pdfs"), exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)


def get_paths(data_dir: str = "data", assets_dir: str = "assets"):
    ensure_dirs(data_dir, assets_dir)
    return {
        "cirugias": os.path.join(data_dir, "cirugias.csv"),
        "firmas_dir": os.path.join(data_dir, "firmas"),
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
    return df


def save_cirugias(df: pd.DataFrame, csv_path: str):
    df.to_csv(csv_path, index=False)


def next_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1
    return int(df["id"].max()) + 1


def find_index(df: pd.DataFrame, cirugia_id: int):
    matches = df.index[df["id"] == int(cirugia_id)].tolist()
    return matches[0] if matches else None


def update_cirugia(df: pd.DataFrame, cirugia_id: int, changes: dict) -> pd.DataFrame:
    idx = find_index(df, cirugia_id)
    if idx is None:
        return df
    for key, value in changes.items():
        df.at[idx, key] = value
    return df


def req_label(text: str):
    st.markdown(
        f"<div style='font-weight:600'>{text} <span style='color:#d11a2a'>*</span></div>",
        unsafe_allow_html=True,
    )


def show_errors(errors):
    for err in errors:
        st.error(err)


def show_warnings(warnings):
    for warn in warnings:
        st.warning(warn)


def signature_widget(label: str, key_base: str, save_path: str) -> str:
    st.markdown(f"**{label}** <span style='color:#d11a2a'>*</span>", unsafe_allow_html=True)

    canvas_session_key = f"canvas_key_{key_base}"
    if canvas_session_key not in st.session_state:
        st.session_state[canvas_session_key] = f"{key_base}_{uuid.uuid4().hex}"

    canvas_key = st.session_state[canvas_session_key]

    canvas_result = st_canvas(
        fill_color="rgba(255,255,255,0)",
        stroke_width=2,
        stroke_color="#000000",
        background_color="#FFFFFF",
        height=160,
        width=320,
        drawing_mode="freedraw",
        key=canvas_key,
        display_toolbar=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Guardar firma", key=f"guardar_{key_base}"):
            if canvas_result.image_data is None:
                st.error("No se detectó firma.")
            else:
                image_array = canvas_result.image_data.astype("uint8")
                if np.all(image_array[:, :, :3] == 255):
                    st.error("La firma está vacía.")
                else:
                    Image.fromarray(image_array).save(save_path)
                    st.session_state[f"ruta_firma_{key_base}"] = save_path
                    st.success("Firma guardada")

    with col2:
        if st.button("Realizar firma", key=f"reiniciar_{key_base}"):
            if os.path.exists(save_path):
                os.remove(save_path)
            st.session_state.pop(f"ruta_firma_{key_base}", None)
            st.session_state[canvas_session_key] = f"{key_base}_{uuid.uuid4().hex}"
            st.rerun()

    final_path = st.session_state.get(f"ruta_firma_{key_base}", "")
    if final_path and os.path.exists(final_path):
        st.image(final_path, caption="Firma guardada", width=220)

    return final_path


def validate_preop(data: dict):
    errors = []
    warnings = []

    required_checks = [
        ("identificacion_confirmada", "Debe confirmar la identidad del paciente."),
        ("manilla_seguridad", "Debe confirmar la manilla de seguridad."),
        ("procedimiento_confirmado", "Debe confirmar el procedimiento y el sitio quirúrgico."),
        ("consentimiento_informado", "No puede continuar sin consentimiento informado firmado y vigente."),
        ("historia_clinica_revisada", "Debe revisar la historia clínica."),
        ("alergias_verificadas", "Debe verificar las alergias."),
        ("ayuno_adecuado", "Debe confirmar el ayuno adecuado."),
        ("sitio_preparado", "Debe confirmar la preparación del sitio quirúrgico."),
        ("instrumental_verificado", "Debe verificar el instrumental."),
    ]

    for field, message in required_checks:
        if not data.get(field, False):
            errors.append(message)

    if not str(data.get("sitio_quirurgico", "")).strip():
        errors.append("El sitio de incisión o miembro es obligatorio.")

    if data.get("sitio_quirurgico") == "Especifique" and not str(data.get("sitio_especificado", "")).strip():
        errors.append("Debe especificar el sitio quirúrgico.")

    if data.get("tiene_alergias") == "Sí" and not str(data.get("detalle_alergias", "")).strip():
        errors.append("Debe especificar las alergias identificadas.")

    if not str(data.get("equipo_utilizado", "")).strip():
        errors.append("Debe registrar el equipo utilizado.")

    if int(data.get("cantidad_instrumentos", 0) or 0) <= 0:
        errors.append("La cantidad de instrumentos debe ser mayor que cero.")

    if not data.get("fecha_esterilizacion"):
        errors.append("Debe registrar la fecha de esterilización del equipo.")

    if not data.get("fecha_vencimiento"):
        errors.append("Debe registrar la fecha de vencimiento del equipo.")

    if data.get("fecha_esterilizacion") and data.get("fecha_vencimiento"):
        fecha_ester = datetime.strptime(str(data["fecha_esterilizacion"]), "%Y-%m-%d").date()
        fecha_venc = datetime.strptime(str(data["fecha_vencimiento"]), "%Y-%m-%d").date()

        if fecha_venc < fecha_ester + timedelta(days=90):
            errors.append(
                "La fecha de vencimiento del equipo debe ser por lo menos 3 meses mayor a la fecha de esterilización."
            )
        elif fecha_venc == fecha_ester + timedelta(days=90):
            warnings.append(
                "Alerta, la fecha de vencimiento del equipo está exactamente en el límite mínimo permitido de 3 meses."
            )

    return errors, warnings


def validate_intraop(data: dict):
    errors = []

    required_checks = [
        ("esterilidad_campo", "Debe confirmar la esterilidad del campo."),
        ("conteo_correcto", "Debe confirmar el conteo de gasas y compresas."),
        ("posicion_confirmada", "Debe confirmar la posición del paciente."),
        ("medicacion_registrada", "Debe registrar y confirmar la medicación administrada."),
        ("equipos_funcionando", "Debe confirmar el funcionamiento de equipos."),
        ("tiempo_registrado", "Debe registrar el tiempo quirúrgico."),
    ]

    for field, message in required_checks:
        if not data.get(field, False):
            errors.append(message)

    if not str(data.get("posicion_paciente", "")).strip():
        errors.append("Debe seleccionar la posición del paciente.")

    if not str(data.get("medicacion_tipo", "")).strip():
        errors.append("Debe registrar el tipo de medicamento administrado.")

    if not str(data.get("medicacion_dosis", "")).strip():
        errors.append("Debe registrar la dosis del medicamento administrado.")

    try:
        h1 = datetime.strptime(str(data.get("hora_inicio", "")), "%H:%M")
        h2 = datetime.strptime(str(data.get("hora_fin", "")), "%H:%M")
        if h2 <= h1:
            errors.append("La hora final debe ser mayor que la hora inicial.")
    except Exception:
        errors.append("Debe registrar una hora de inicio y una hora final válidas.")

    if data.get("hubo_incidencias") == "Sí":
        if not str(data.get("detalle_incidencias", "")).strip():
            errors.append("Debe describir las incidencias ocurridas.")
        if not data.get("incidencias_registradas", False):
            errors.append("Debe confirmar el registro de incidencias.")

    return errors


def validate_postop(data: dict):
    errors = []

    required_checks = [
        ("indicaciones_ok", "Debe confirmar las indicaciones postoperatorias."),
        ("comunicacion_recuperacion_ok", "Debe confirmar la comunicación con recuperación."),
        ("registro_medicamentos_ok", "Debe confirmar el registro de medicamentos."),
        ("drenajes_ok", "Debe confirmar la verificación de drenajes y sondas."),
        ("dolor_ok", "Debe confirmar el control del dolor."),
        ("conciencia_ok", "Debe confirmar el control de conciencia."),
        ("signos_ok", "Debe confirmar el registro de signos vitales."),
    ]

    for field, message in required_checks:
        if not data.get(field, False):
            errors.append(message)

    if not str(data.get("signos_vitales", "")).strip():
        errors.append("Debe registrar los signos vitales.")

    return errors


def draw_signature_pdf(c, x, y, title, image_path):
    width_img = 140
    height_img = 45

    if image_path and os.path.exists(image_path):
        c.drawImage(
            ImageReader(image_path),
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
    pre = from_json(row["datos_preop"])
    intra = from_json(row["datos_intraop"])
    post = from_json(row["datos_postop"])

    file_name = f"checklist_cirugia_{int(row['id'])}.pdf"
    pdf_path = os.path.join(pdfs_dir, file_name)

    c = pdf_canvas.Canvas(pdf_path, pagesize=landscape(A4))
    page_width, page_height = landscape(A4)

    c.setFillColor(colors.HexColor("#EAF2FF"))
    c.rect(0, page_height - 80, page_width, 80, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#123B6D"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(30, page_height - 30, "Checklist de Cirugía Segura")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(30, page_height - 48, f"Paciente: {row['nombre_paciente']}")
    c.drawString(30, page_height - 62, f"Documento: {row['tipo_documento']} {row['numero_documento']}")
    c.drawString(250, page_height - 48, f"Edad: {row['edad']}")
    c.drawString(250, page_height - 62, f"Institución: {row['institucion']}")
    c.drawString(470, page_height - 48, f"Fecha: {row['fecha_cirugia']}")
    c.drawString(470, page_height - 62, f"Procedimiento: {row['procedimiento']}")

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

    draw_signature_pdf(c, 35, 45, "Aux. enfermería circulante", row["firma_aux_circulante"])
    draw_signature_pdf(c, 225, 45, "Instrumentador/a QX", row["firma_instrumentador"])
    draw_signature_pdf(c, 415, 45, "Cirujano/a", row["firma_cirujano"])
    draw_signature_pdf(c, 605, 45, "Anestesiólogo/a", row["firma_anestesiologo"])

    c.save()
    return pdf_path


def render_cirugia(data_dir: str = "data", assets_dir: str = "assets"):
    paths = get_paths(data_dir, assets_dir)
    cirugias = load_cirugias(paths["cirugias"])

    st.title("🏥 Cirugía Segura")

    tab_ingreso, tab_checklist = st.tabs(["1. Ingreso del paciente", "2. Checklist, firmas y PDF"])

    with tab_ingreso:
        st.subheader("Ingreso del paciente")

        with st.form("form_ingreso_cirugia"):
            c1, c2, c3 = st.columns(3)
            with c1:
                req_label("Nombre del paciente")
                nombre_paciente = st.text_input("nombre_paciente", label_visibility="collapsed")
            with c2:
                req_label("No. de documento")
                numero_documento = st.text_input("numero_documento", label_visibility="collapsed")
            with c3:
                req_label("Institución")
                institucion = st.text_input("institucion", label_visibility="collapsed")

            c4, c5, c6, c7 = st.columns(4)
            with c4:
                req_label("Tipo de documento")
                tipo_documento = st.selectbox("tipo_documento", TIPOS_DOCUMENTO, label_visibility="collapsed")
            with c5:
                req_label("Edad")
                edad = st.number_input("edad", min_value=0, max_value=120, step=1, label_visibility="collapsed")
            with c6:
                req_label("Fecha")
                fecha_cirugia = st.date_input("fecha_cirugia", date.today(), label_visibility="collapsed")
            with c7:
                req_label("Procedimiento")
                procedimiento = st.text_input("procedimiento", label_visibility="collapsed")

            guardar_ingreso = st.form_submit_button("Guardar ingreso del paciente")

            if guardar_ingreso:
                errors = []
                if not nombre_paciente.strip():
                    errors.append("El nombre del paciente es obligatorio.")
                if not numero_documento.strip():
                    errors.append("El número de documento es obligatorio.")
                if not institucion.strip():
                    errors.append("La institución es obligatoria.")
                if int(edad) <= 0:
                    errors.append("La edad debe ser mayor que cero.")
                if not procedimiento.strip():
                    errors.append("El procedimiento es obligatorio.")

                if errors:
                    show_errors(errors)
                else:
                    new_id = next_id(cirugias)
                    new_row = pd.DataFrame([
                        {
                            "id": new_id,
                            "nombre_paciente": nombre_paciente.strip(),
                            "numero_documento": numero_documento.strip(),
                            "institucion": institucion.strip(),
                            "tipo_documento": tipo_documento,
                            "edad": int(edad),
                            "fecha_cirugia": str(fecha_cirugia),
                            "procedimiento": procedimiento.strip(),
                            "checklist_iniciado": False,
                            "preop_completa": False,
                            "firmas_preop_completas": False,
                            "intraop_completa": False,
                            "postop_completa": False,
                            "datos_preop": "",
                            "datos_intraop": "",
                            "datos_postop": "",
                            "firma_aux_circulante": "",
                            "firma_instrumentador": "",
                            "firma_cirujano": "",
                            "firma_anestesiologo": "",
                        }
                    ])
                    cirugias = pd.concat([cirugias, new_row], ignore_index=True)
                    save_cirugias(cirugias, paths["cirugias"])
                    st.session_state["cirugia_activa_id"] = new_id
                    st.success("Ingreso del paciente registrado correctamente.")
                    st.rerun()

        if not cirugias.empty:
            st.divider()
            st.subheader("Cirugías registradas")
            st.dataframe(
                cirugias[
                    [
                        "id",
                        "nombre_paciente",
                        "numero_documento",
                        "fecha_cirugia",
                        "procedimiento",
                        "preop_completa",
                        "firmas_preop_completas",
                        "intraop_completa",
                        "postop_completa",
                    ]
                ],
                use_container_width=True,
            )

    with tab_checklist:
        if cirugias.empty:
            st.warning("Primero debes registrar el ingreso del paciente.")
            return

        ids = cirugias["id"].tolist()
        default_id = st.session_state.get("cirugia_activa_id", ids[-1])
        if default_id not in ids:
            default_id = ids[-1]
        default_pos = ids.index(default_id)

        cirugia_id = st.selectbox(
            "Seleccione la cirugía",
            options=ids,
            index=default_pos,
            format_func=lambda x: (
                f"Cirugía #{x} | "
                f"{cirugias.loc[cirugias['id'] == x, 'nombre_paciente'].iloc[0]} | "
                f"{cirugias.loc[cirugias['id'] == x, 'procedimiento'].iloc[0]}"
            ),
        )
        st.session_state["cirugia_activa_id"] = cirugia_id

        current = load_cirugias(paths["cirugias"])
        row = current[current["id"] == cirugia_id].iloc[0]
        preop = from_json(row["datos_preop"])
        intraop = from_json(row["datos_intraop"])
        postop = from_json(row["datos_postop"])

        st.info(
            f"Paciente: {row['nombre_paciente']} | Documento: {row['tipo_documento']} {row['numero_documento']} | "
            f"Edad: {row['edad']} | Fecha: {row['fecha_cirugia']} | Procedimiento: {row['procedimiento']}"
        )

        if not row["checklist_iniciado"]:
            if st.button("▶️ Dar inicio a checklist"):
                current = update_cirugia(current, cirugia_id, {"checklist_iniciado": True})
                save_cirugias(current, paths["cirugias"])
                st.success("Checklist iniciado.")
                st.rerun()

            st.warning("Debes iniciar el checklist para habilitar las fases.")
            return

        st.success("Checklist en proceso")

        st.subheader("Fase preoperatoria")
        with st.form(f"form_preop_{cirugia_id}"):
            a1, a2 = st.columns(2)

            with a1:
                st.markdown("**1. Identificación del paciente**")
                identificacion_confirmada = st.checkbox(
                    "Identidad confirmada",
                    value=preop.get("identificacion_confirmada", False),
                )
                manilla_seguridad = st.checkbox(
                    "Manilla de seguridad verificada",
                    value=preop.get("manilla_seguridad", False),
                )

                st.markdown("**2. Confirmación del procedimiento**")
                current_site = preop.get("sitio_quirurgico", "")
                sitio_quirurgico = st.selectbox(
                    "Sitio de incisión / miembro",
                    SITIOS_QUIRURGICOS,
                    index=SITIOS_QUIRURGICOS.index(current_site) if current_site in SITIOS_QUIRURGICOS else 0,
                )
                sitio_especificado = st.text_input(
                    "Especifique sitio",
                    value=preop.get("sitio_especificado", ""),
                    disabled=(sitio_quirurgico != "Especifique"),
                )
                procedimiento_confirmado = st.checkbox(
                    "Procedimiento y sitio confirmados",
                    value=preop.get("procedimiento_confirmado", False),
                )

                st.markdown("**3. Consentimiento informado**")
                consentimiento_informado = st.checkbox(
                    "Consentimiento informado firmado y vigente",
                    value=preop.get("consentimiento_informado", False),
                )

                st.markdown("**4. Revisión de historia clínica**")
                historia_clinica_revisada = st.checkbox(
                    "Historia clínica revisada",
                    value=preop.get("historia_clinica_revisada", False),
                )

            with a2:
                st.markdown("**5. Alergias**")
                stored_has_allergies = preop.get("tiene_alergias", "No")
                tiene_alergias = st.radio(
                    "¿Presenta alergias?",
                    ["No", "Sí"],
                    index=1 if stored_has_allergies == "Sí" else 0,
                    horizontal=True,
                )
                detalle_alergias = st.text_input(
                    "Especifique las alergias identificadas",
                    value=preop.get("detalle_alergias", "") if stored_has_allergies == "Sí" else "",
                    disabled=(tiene_alergias == "No"),
                )
                alergias_verificadas = st.checkbox(
                    "Alergias verificadas",
                    value=preop.get("alergias_verificadas", False),
                )

                st.markdown("**6. Ayuno adecuado**")
                ayuno_adecuado = st.checkbox(
                    "Ayuno adecuado confirmado",
                    value=preop.get("ayuno_adecuado", False),
                )

                st.markdown("**7. Preparación del sitio quirúrgico**")
                sitio_preparado = st.checkbox(
                    "Sitio quirúrgico preparado correctamente",
                    value=preop.get("sitio_preparado", False),
                )

                st.markdown("**8. Verificación del instrumental**")
                equipo_utilizado = st.text_input(
                    "Equipo utilizado",
                    value=preop.get("equipo_utilizado", ""),
                )
                cantidad_instrumentos = st.number_input(
                    "Cantidad de instrumentos",
                    min_value=0,
                    step=1,
                    value=int(preop.get("cantidad_instrumentos", 0) or 0),
                )

                stored_ester = preop.get("fecha_esterilizacion", str(date.today()))
                fecha_esterilizacion = st.date_input(
                    "Fecha de esterilización",
                    value=datetime.strptime(stored_ester, "%Y-%m-%d").date() if stored_ester else date.today(),
                )

                min_vencimiento = fecha_esterilizacion + timedelta(days=90)
                stored_venc = preop.get("fecha_vencimiento", str(min_vencimiento))
                stored_venc_date = datetime.strptime(stored_venc, "%Y-%m-%d").date() if stored_venc else min_vencimiento
                if stored_venc_date < min_vencimiento:
                    stored_venc_date = min_vencimiento

                fecha_vencimiento = st.date_input(
                    "Fecha de vencimiento del equipo",
                    value=stored_venc_date,
                    min_value=min_vencimiento,
                )

                instrumental_verificado = st.checkbox(
                    "Instrumental verificado",
                    value=preop.get("instrumental_verificado", False),
                )

            save_preop = st.form_submit_button("Guardar fase preoperatoria")
            if save_preop:
                data_preop = {
                    "fecha_cirugia": str(row["fecha_cirugia"]),
                    "identificacion_confirmada": identificacion_confirmada,
                    "manilla_seguridad": manilla_seguridad,
                    "sitio_quirurgico": sitio_quirurgico,
                    "sitio_especificado": sitio_especificado.strip() if sitio_quirurgico == "Especifique" else "",
                    "procedimiento_confirmado": procedimiento_confirmado,
                    "consentimiento_informado": consentimiento_informado,
                    "historia_clinica_revisada": historia_clinica_revisada,
                    "tiene_alergias": tiene_alergias,
                    "detalle_alergias": detalle_alergias.strip() if tiene_alergias == "Sí" else "",
                    "alergias_verificadas": alergias_verificadas,
                    "ayuno_adecuado": ayuno_adecuado,
                    "sitio_preparado": sitio_preparado,
                    "equipo_utilizado": equipo_utilizado.strip(),
                    "cantidad_instrumentos": int(cantidad_instrumentos),
                    "fecha_esterilizacion": str(fecha_esterilizacion),
                    "fecha_vencimiento": str(fecha_vencimiento),
                    "instrumental_verificado": instrumental_verificado,
                }

                errors, warnings = validate_preop(data_preop)
                if errors:
                    show_errors(errors)
                else:
                    if warnings:
                        show_warnings(warnings)
                    current = update_cirugia(
                        current,
                        cirugia_id,
                        {
                            "datos_preop": to_json(data_preop),
                            "preop_completa": True,
                        },
                    )
                    save_cirugias(current, paths["cirugias"])
                    st.success("Fase preoperatoria completada.")
                    st.rerun()

        current = load_cirugias(paths["cirugias"])
        row = current[current["id"] == cirugia_id].iloc[0]

        st.divider()
        st.subheader("Firmas de confirmación, obligatorias antes de la fase intraoperatoria")

        if not row["preop_completa"]:
            st.warning("Debes completar la fase preoperatoria para habilitar las firmas.")
        else:
            b1, b2 = st.columns(2)
            with b1:
                aux_path = os.path.join(paths["firmas_dir"], f"firma_aux_{cirugia_id}.png")
                firma_aux = signature_widget("Aux. enfermería circulante en sala", f"aux_{cirugia_id}", aux_path)

                instr_path = os.path.join(paths["firmas_dir"], f"firma_instr_{cirugia_id}.png")
                firma_instr = signature_widget("Instrumentador/a QX de la sala", f"instr_{cirugia_id}", instr_path)

            with b2:
                cir_path = os.path.join(paths["firmas_dir"], f"firma_cir_{cirugia_id}.png")
                firma_cir = signature_widget("Cirujano/a", f"cir_{cirugia_id}", cir_path)

                anes_path = os.path.join(paths["firmas_dir"], f"firma_anes_{cirugia_id}.png")
                firma_anes = signature_widget("Anestesiólogo/a", f"anes_{cirugia_id}", anes_path)

            if st.button("Confirmar firmas preoperatorias"):
                sign_errors = []
                if not firma_aux or not os.path.exists(firma_aux):
                    sign_errors.append("Falta la firma del auxiliar circulante.")
                if not firma_instr or not os.path.exists(firma_instr):
                    sign_errors.append("Falta la firma del instrumentador/a.")
                if not firma_cir or not os.path.exists(firma_cir):
                    sign_errors.append("Falta la firma del cirujano/a.")
                if not firma_anes or not os.path.exists(firma_anes):
                    sign_errors.append("Falta la firma del anestesiólogo/a.")

                if sign_errors:
                    show_errors(sign_errors)
                else:
                    current = update_cirugia(
                        current,
                        cirugia_id,
                        {
                            "firma_aux_circulante": firma_aux,
                            "firma_instrumentador": firma_instr,
                            "firma_cirujano": firma_cir,
                            "firma_anestesiologo": firma_anes,
                            "firmas_preop_completas": True,
                        },
                    )
                    save_cirugias(current, paths["cirugias"])
                    st.success("Firmas confirmadas. Ya puedes avanzar a la fase intraoperatoria.")
                    st.rerun()

        current = load_cirugias(paths["cirugias"])
        row = current[current["id"] == cirugia_id].iloc[0]
        intraop = from_json(row["datos_intraop"])

        st.divider()
        st.subheader("Fase intraoperatoria")

        if not row["firmas_preop_completas"]:
            st.warning("Debes completar la fase preoperatoria y las firmas para habilitar la fase intraoperatoria.")
        else:
            with st.form(f"form_intraop_{cirugia_id}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**1. Esterilidad del campo**")
                    esterilidad_campo = st.checkbox(
                        "Esterilidad del campo confirmada",
                        value=intraop.get("esterilidad_campo", False),
                    )

                    st.markdown("**2. Conteo de gasas y compresas**")
                    gasas_inicio = st.number_input("Gasas al inicio", min_value=0, step=1, value=int(intraop.get("gasas_inicio", 0) or 0))
                    gasas_cierre = st.number_input("Gasas al cierre", min_value=0, step=1, value=int(intraop.get("gasas_cierre", 0) or 0))
                    compresas_inicio = st.number_input(
                        "Compresas al inicio", min_value=0, step=1, value=int(intraop.get("compresas_inicio", 0) or 0)
                    )
                    compresas_cierre = st.number_input(
                        "Compresas al cierre", min_value=0, step=1, value=int(intraop.get("compresas_cierre", 0) or 0)
                    )
                    conteo_correcto = st.checkbox(
                        "Conteo correcto confirmado",
                        value=intraop.get("conteo_correcto", False),
                    )

                    st.markdown("**3. Posición del paciente**")
                    current_position = intraop.get("posicion_paciente", "")
                    posicion_paciente = st.selectbox(
                        "Posición del paciente",
                        POSICIONES_PACIENTE,
                        index=POSICIONES_PACIENTE.index(current_position) if current_position in POSICIONES_PACIENTE else 0,
                    )
                    posicion_confirmada = st.checkbox(
                        "Posición confirmada",
                        value=intraop.get("posicion_confirmada", False),
                    )

                with c2:
                    st.markdown("**4. Medicación administrada**")
                    medicacion_tipo = st.text_input(
                        "Tipo de medicamento",
                        value=intraop.get("medicacion_tipo", ""),
                    )
                    medicacion_dosis = st.text_input(
                        "Dosis",
                        value=intraop.get("medicacion_dosis", ""),
                    )
                    medicacion_registrada = st.checkbox(
                        "Medicación registrada",
                        value=intraop.get("medicacion_registrada", False),
                    )

                    st.markdown("**5. Funcionamiento de equipos**")
                    equipos_funcionando = st.checkbox(
                        "Equipos biomédicos y quirúrgicos funcionando",
                        value=intraop.get("equipos_funcionando", False),
                    )

                    st.markdown("**6. Control del tiempo quirúrgico**")
                    hora_inicio = st.time_input(
                        "Hora de inicio",
                        value=datetime.strptime(intraop.get("hora_inicio", "08:00"), "%H:%M").time(),
                    )
                    hora_fin = st.time_input(
                        "Hora final",
                        value=datetime.strptime(intraop.get("hora_fin", "09:00"), "%H:%M").time(),
                    )
                    tiempo_registrado = st.checkbox(
                        "Tiempo quirúrgico registrado",
                        value=intraop.get("tiempo_registrado", False),
                    )

                    st.markdown("**7. Registro de incidencias**")
                    stored_inc = intraop.get("hubo_incidencias", "No")
                    hubo_incidencias = st.radio(
                        "¿Hubo incidencias?",
                        ["No", "Sí"],
                        index=1 if stored_inc == "Sí" else 0,
                        horizontal=True,
                    )
                    detalle_incidencias = st.text_area(
                        "Detalle de incidencias",
                        value=intraop.get("detalle_incidencias", "") if stored_inc == "Sí" else "",
                        height=100,
                        disabled=(hubo_incidencias == "No"),
                    )
                    incidencias_registradas = st.checkbox(
                        "Incidencias registradas",
                        value=intraop.get("incidencias_registradas", False) if stored_inc == "Sí" else True,
                        disabled=(hubo_incidencias == "No"),
                    )

                save_intra = st.form_submit_button("Guardar fase intraoperatoria")
                if save_intra:
                    data_intra = {
                        "esterilidad_campo": esterilidad_campo,
                        "gasas_inicio": int(gasas_inicio),
                        "gasas_cierre": int(gasas_cierre),
                        "compresas_inicio": int(compresas_inicio),
                        "compresas_cierre": int(compresas_cierre),
                        "conteo_correcto": conteo_correcto,
                        "posicion_paciente": posicion_paciente,
                        "posicion_confirmada": posicion_confirmada,
                        "medicacion_tipo": medicacion_tipo.strip(),
                        "medicacion_dosis": medicacion_dosis.strip(),
                        "medicacion_registrada": medicacion_registrada,
                        "equipos_funcionando": equipos_funcionando,
                        "hora_inicio": hora_inicio.strftime("%H:%M"),
                        "hora_fin": hora_fin.strftime("%H:%M"),
                        "tiempo_registrado": tiempo_registrado,
                        "hubo_incidencias": hubo_incidencias,
                        "detalle_incidencias": detalle_incidencias.strip() if hubo_incidencias == "Sí" else "",
                        "incidencias_registradas": incidencias_registradas if hubo_incidencias == "Sí" else True,
                    }

                    errors = validate_intraop(data_intra)
                    if errors:
                        show_errors(errors)
                    else:
                        current = update_cirugia(
                            current,
                            cirugia_id,
                            {
                                "datos_intraop": to_json(data_intra),
                                "intraop_completa": True,
                            },
                        )
                        save_cirugias(current, paths["cirugias"])
                        st.success("Fase intraoperatoria completada.")
                        st.rerun()

        current = load_cirugias(paths["cirugias"])
        row = current[current["id"] == cirugia_id].iloc[0]
        postop = from_json(row["datos_postop"])

        st.divider()
        st.subheader("Fase postoperatoria")

        if not row["intraop_completa"]:
            st.warning("Debes completar la fase intraoperatoria para habilitar la fase postoperatoria.")
        else:
            with st.form(f"form_postop_{cirugia_id}"):
                st.markdown("**Fase postoperatoria**")

                indicaciones_ok = st.checkbox(
                    "1. Indicaciones postoperatorias verificadas",
                    value=postop.get("indicaciones_ok", False),
                )
                comunicacion_recuperacion_ok = st.checkbox(
                    "2. Comunicación con recuperación realizada",
                    value=postop.get("comunicacion_recuperacion_ok", False),
                )
                registro_medicamentos_ok = st.checkbox(
                    "3. Registro de medicamentos realizado",
                    value=postop.get("registro_medicamentos_ok", False),
                )
                drenajes_ok = st.checkbox(
                    "4. Verificación de drenajes y sondas realizada",
                    value=postop.get("drenajes_ok", False),
                )
                dolor_ok = st.checkbox(
                    "5. Control del dolor realizado",
                    value=postop.get("dolor_ok", False),
                )
                conciencia_ok = st.checkbox(
                    "6. Control de conciencia realizado",
                    value=postop.get("conciencia_ok", False),
                )
                signos_vitales = st.text_area(
                    "7. Signos vitales",
                    value=postop.get("signos_vitales", ""),
                    height=100,
                )
                signos_ok = st.checkbox(
                    "Signos vitales confirmados",
                    value=postop.get("signos_ok", False),
                )

                save_post = st.form_submit_button("Guardar fase postoperatoria")
                if save_post:
                    data_post = {
                        "indicaciones_ok": indicaciones_ok,
                        "comunicacion_recuperacion_ok": comunicacion_recuperacion_ok,
                        "registro_medicamentos_ok": registro_medicamentos_ok,
                        "drenajes_ok": drenajes_ok,
                        "dolor_ok": dolor_ok,
                        "conciencia_ok": conciencia_ok,
                        "signos_vitales": signos_vitales.strip(),
                        "signos_ok": signos_ok,
                    }

                    errors = validate_postop(data_post)
                    if errors:
                        show_errors(errors)
                    else:
                        current = update_cirugia(
                            current,
                            cirugia_id,
                            {
                                "datos_postop": to_json(data_post),
                                "postop_completa": True,
                            },
                        )
                        save_cirugias(current, paths["cirugias"])
                        st.success("Fase postoperatoria completada.")
                        st.rerun()

        current = load_cirugias(paths["cirugias"])
        row = current[current["id"] == cirugia_id].iloc[0]

        st.divider()
        st.subheader("Exportar PDF")
        if row["preop_completa"] and row["firmas_preop_completas"] and row["intraop_completa"] and row["postop_completa"]:
            st.success("Checklist completo. Ya puedes exportar el PDF.")
            if st.button("📄 Generar PDF horizontal"):
                pdf_path = export_pdf(row, paths["pdfs_dir"], paths["logo"])
                with open(pdf_path, "rb") as file:
                    st.download_button(
                        label="📥 Descargar PDF",
                        data=file,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf",
                    )
        else:
            st.warning("Debes completar todas las fases y las firmas para habilitar la exportación del PDF.")


if __name__ == "__main__":
    render_cirugia()
