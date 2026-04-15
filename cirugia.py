import os
import json
import re
import uuid
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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

TIPOS_DOCUMENTO = ["R.C", "T.I", "C.C", "OTRO"]
SEXOS = ["", "Masculino", "Femenino", "Otro"]
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


def normalize_document(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
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
        "historia": os.path.join(data_dir, "historia_clinica.csv"),
        "pacientes": os.path.join(data_dir, "pacientes.csv"),
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
    if "numero_documento" in df.columns:
        df["numero_documento"] = df["numero_documento"].apply(normalize_document)
    return df


def save_cirugias(df: pd.DataFrame, csv_path: str):
    df.to_csv(csv_path, index=False)


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


def upsert_checklist_historia(historia_csv: str, row: pd.Series, pdf_path: str):
    historia = load_historia(historia_csv)
    mask = (historia["tipo_registro"] == "Checklist cirugía segura") & (historia["cirugia_id"] == int(row["id"]))
    payload = {
        "tipo_registro": "Checklist cirugía segura",
        "cirugia_id": int(row["id"]),
        "paciente": str(row.get("nombre_paciente", "")),
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_cirugia": str(row.get("fecha_cirugia", "")),
        "procedimiento": str(row.get("procedimiento", "")),
        "motivo": "Checklist quirúrgico generado",
        "diagnostico": "",
        "antecedentes": "",
        "observaciones": "PDF de checklist generado y archivado.",
        "pdf_checklist": pdf_path,
    }
    if mask.any():
        idx = historia.index[mask][0]
        for k, v in payload.items():
            historia.at[idx, k] = v
    else:
        next_historia_id = 1 if historia.empty else int(historia["id"].max()) + 1
        payload["id"] = next_historia_id
        historia = pd.concat([historia, pd.DataFrame([payload])], ignore_index=True)
    save_historia(historia, historia_csv)


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


def play_alert_sound():
    components.html(
        """
        <script>
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          const ctx = new AudioCtx();
          const now = ctx.currentTime;

          const osc1 = ctx.createOscillator();
          const gain1 = ctx.createGain();
          osc1.type = "square";
          osc1.frequency.setValueAtTime(1046, now);
          gain1.gain.setValueAtTime(0.18, now);
          gain1.gain.exponentialRampToValueAtTime(0.0001, now + 0.24);
          osc1.connect(gain1);
          gain1.connect(ctx.destination);
          osc1.start(now);
          osc1.stop(now + 0.24);

          const osc2 = ctx.createOscillator();
          const gain2 = ctx.createGain();
          osc2.type = "square";
          osc2.frequency.setValueAtTime(1318, now + 0.12);
          gain2.gain.setValueAtTime(0.16, now + 0.12);
          gain2.gain.exponentialRampToValueAtTime(0.0001, now + 0.42);
          osc2.connect(gain2);
          gain2.connect(ctx.destination);
          osc2.start(now + 0.12);
          osc2.stop(now + 0.42);
        }
        </script>
        """,
        height=0,
    )


def show_errors(errors):
    if errors:
        play_alert_sound()
    for err in errors:
        st.error(err)


def show_warnings(warnings):
    if warnings:
        play_alert_sound()
    for warn in warnings:
        st.warning(warn)


def alert_warning(message: str):
    play_alert_sound()
    st.warning(message)


def ss_init(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default


def reset_widget_on_next_run(widget_key: str):
    st.session_state[f"__reset__{widget_key}"] = True


def apply_widget_reset(widget_key: str):
    reset_key = f"__reset__{widget_key}"
    if st.session_state.pop(reset_key, False):
        st.session_state.pop(widget_key, None)


DRAFT_KEY = "cirugia_borrador"


def empty_draft():
    return {
        "draft_id": uuid.uuid4().hex,
        "nombre_paciente": "",
        "numero_documento": "",
        "institucion": "",
        "tipo_documento": "",
        "fecha_nacimiento": "",
        "sexo": "",
        "edad": 0,
        "fecha_cirugia": str(date.today()),
        "procedimiento": "",
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
        "pdf_checklist": "",
        "fecha_pdf_checklist": "",
    }


def get_draft():
    if DRAFT_KEY not in st.session_state:
        st.session_state[DRAFT_KEY] = empty_draft()
    return st.session_state[DRAFT_KEY]


def save_draft(data: dict):
    st.session_state[DRAFT_KEY] = data


def clear_draft():
    st.session_state[DRAFT_KEY] = empty_draft()
    st.session_state["cirugia_modo_borrador"] = False


def draft_has_data() -> bool:
    draft = get_draft()
    return bool(str(draft.get("nombre_paciente", "")).strip())


def draft_as_series():
    draft = get_draft().copy()
    draft.setdefault("id", 0)
    return pd.Series(draft)


def set_pending_step(case_key: str, next_step: str):
    st.session_state[f"pending_step_cirugia_{case_key}"] = next_step


def calculate_age(fecha_nacimiento):
    if not fecha_nacimiento:
        return 0
    hoy = date.today()
    return hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))


def normalize_patients_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["nombre_paciente", "numero_documento", "institucion", "tipo_documento", "fecha_nacimiento", "sexo"])

    rename_map = {}
    columns = {c.lower().strip(): c for c in df.columns}
    candidates = {
        "nombre_paciente": ["nombre_paciente", "nombre", "paciente", "nombres", "nombre completo"],
        "numero_documento": ["numero_documento", "documento", "cedula", "cédula", "identificacion", "identificación"],
        "institucion": ["institucion", "institución", "eps", "entidad"],
        "tipo_documento": ["tipo_documento", "tipo doc", "tipo", "documento_tipo"],
        "fecha_nacimiento": ["fecha_nacimiento", "fecha de nacimiento", "nacimiento", "f_nacimiento"],
        "sexo": ["sexo", "género", "genero"],
    }
    for target, options in candidates.items():
        for opt in options:
            if opt in columns:
                rename_map[columns[opt]] = target
                break
    df = df.rename(columns=rename_map).copy()
    for col in ["nombre_paciente", "numero_documento", "institucion", "tipo_documento", "fecha_nacimiento", "sexo"]:
        if col not in df.columns:
            df[col] = ""
    df = df[["nombre_paciente", "numero_documento", "institucion", "tipo_documento", "fecha_nacimiento", "sexo"]].copy()
    df["numero_documento"] = df["numero_documento"].apply(normalize_document)
    df["nombre_paciente"] = df["nombre_paciente"].fillna("").astype(str).str.strip()
    return df


def load_pacientes(paths: dict) -> pd.DataFrame:
    sources = []
    if os.path.exists(paths["pacientes"]):
        try:
            sources.append(normalize_patients_df(pd.read_csv(paths["pacientes"])))
        except Exception:
            pass
    cir = load_cirugias(paths["cirugias"])
    if not cir.empty:
        sources.append(normalize_patients_df(cir[["nombre_paciente", "numero_documento", "institucion", "tipo_documento", "fecha_nacimiento", "sexo"]]))
    if not sources:
        return normalize_patients_df(pd.DataFrame())
    df = pd.concat(sources, ignore_index=True).fillna("")
    df["numero_documento"] = df["numero_documento"].apply(normalize_document)
    df["nombre_paciente"] = df["nombre_paciente"].astype(str).str.strip()
    df = df[df["numero_documento"] != ""]
    df = df.drop_duplicates(subset=["numero_documento"], keep="first")
    return df


def find_paciente_by_documento(paths: dict, documento: str):
    documento = normalize_document(documento)
    if not documento:
        return None
    pacientes = load_pacientes(paths)
    if pacientes.empty:
        return None
    mask = pacientes["numero_documento"].apply(normalize_document) == documento
    if mask.any():
        return pacientes[mask].iloc[0].to_dict()
    return None


def update_draft(changes: dict):
    draft = get_draft().copy()
    for k, v in changes.items():
        draft[k] = v
    save_draft(draft)


def finalize_draft_to_cirugia(paths: dict):
    cirugias = load_cirugias(paths["cirugias"])
    draft = get_draft().copy()
    new_id = next_id(cirugias)
    rename_map = {
        "firma_aux_circulante": os.path.join(paths["firmas_dir"], f"firma_aux_{new_id}.png"),
        "firma_instrumentador": os.path.join(paths["firmas_dir"], f"firma_instr_{new_id}.png"),
        "firma_cirujano": os.path.join(paths["firmas_dir"], f"firma_cir_{new_id}.png"),
        "firma_anestesiologo": os.path.join(paths["firmas_dir"], f"firma_anes_{new_id}.png"),
    }
    for field, final_path in rename_map.items():
        current_path = str(draft.get(field, "")).strip()
        if current_path and os.path.exists(current_path):
            if os.path.abspath(current_path) != os.path.abspath(final_path):
                os.replace(current_path, final_path)
            draft[field] = final_path

    row = {col: "" for col in CIRUGIA_COLUMNS}
    row.update({col: False for col in BOOL_COLS})
    row.update({
        "id": new_id,
        "nombre_paciente": draft.get("nombre_paciente", ""),
        "numero_documento": normalize_document(draft.get("numero_documento", "")),
        "institucion": draft.get("institucion", ""),
        "tipo_documento": draft.get("tipo_documento", ""),
        "fecha_nacimiento": draft.get("fecha_nacimiento", ""),
        "sexo": draft.get("sexo", ""),
        "edad": draft.get("edad", 0),
        "fecha_cirugia": draft.get("fecha_cirugia", ""),
        "procedimiento": draft.get("procedimiento", ""),
        "checklist_iniciado": True,
        "preop_completa": draft.get("preop_completa", False),
        "firmas_preop_completas": draft.get("firmas_preop_completas", False),
        "intraop_completa": draft.get("intraop_completa", False),
        "postop_completa": draft.get("postop_completa", False),
        "datos_preop": draft.get("datos_preop", ""),
        "datos_intraop": draft.get("datos_intraop", ""),
        "datos_postop": draft.get("datos_postop", ""),
        "firma_aux_circulante": draft.get("firma_aux_circulante", ""),
        "firma_instrumentador": draft.get("firma_instrumentador", ""),
        "firma_cirujano": draft.get("firma_cirujano", ""),
        "firma_anestesiologo": draft.get("firma_anestesiologo", ""),
        "pdf_checklist": "",
        "fecha_pdf_checklist": "",
    })
    cirugias = pd.concat([cirugias, pd.DataFrame([row])], ignore_index=True)
    save_cirugias(cirugias, paths["cirugias"])
    return new_id


def save_case_changes(case_id, is_draft: bool, current: pd.DataFrame, changes: dict, paths: dict):
    if is_draft:
        update_draft(changes)
        return None
    current = update_cirugia(current, int(case_id), changes)
    save_cirugias(current, paths["cirugias"])
    return current


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
            errors.append("La fecha de vencimiento del equipo debe ser por lo menos 3 meses mayor a la fecha de esterilización.")
        elif fecha_venc == fecha_ester + timedelta(days=90):
            warnings.append("Alerta, la fecha de vencimiento del equipo está exactamente en el límite mínimo permitido de 3 meses.")
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
        c.drawImage(ImageReader(image_path), x, y, width=width_img, height=height_img, preserveAspectRatio=True, mask="auto")
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
    c.rect(0, page_height - 80, page_width, 80, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#123B6D"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(30, page_height - 30, "Checklist de Cirugía Segura")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(30, page_height - 48, f"Paciente: {row.get('nombre_paciente', '')}")
    c.drawString(30, page_height - 62, f"Documento: {row.get('tipo_documento', '')} {row.get('numero_documento', '')}")
    c.drawString(250, page_height - 48, f"Edad: {row.get('edad', '')}")
    c.drawString(250, page_height - 62, f"Institución: {row.get('institucion', '')}")
    c.drawString(470, page_height - 48, f"Fecha cirugía: {row.get('fecha_cirugia', '')}")
    c.drawString(470, page_height - 62, f"Procedimiento: {row.get('procedimiento', '')}")
    c.drawString(30, page_height - 76, f"Fecha nacimiento: {row.get('fecha_nacimiento', '')}")
    c.drawString(250, page_height - 76, f"Sexo: {row.get('sexo', '')}")

    if os.path.exists(logo_path):
        c.drawImage(ImageReader(logo_path), page_width - 120, page_height - 70, width=80, height=50, preserveAspectRatio=True, mask="auto")

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


def get_step_sequence():
    return ["Preoperatoria", "Firmas", "Intraoperatoria", "Postoperatoria", "PDF"]


def get_enabled_steps(row: pd.Series):
    steps = []
    if not row.get("checklist_iniciado", False):
        return steps
    steps.append("Preoperatoria")
    if row.get("preop_completa", False):
        steps.append("Firmas")
    if row.get("firmas_preop_completas", False):
        steps.append("Intraoperatoria")
    if row.get("intraop_completa", False):
        steps.append("Postoperatoria")
    if row.get("postop_completa", False):
        steps.append("PDF")
    return steps


def get_recommended_step(row: pd.Series):
    if not row.get("checklist_iniciado", False):
        return None
    if not row.get("preop_completa", False):
        return "Preoperatoria"
    if not row.get("firmas_preop_completas", False):
        return "Firmas"
    if not row.get("intraop_completa", False):
        return "Intraoperatoria"
    if not row.get("postop_completa", False):
        return "Postoperatoria"
    return "PDF"


def render_step_status(row: pd.Series):
    labels = [
        ("Preoperatoria", row.get("preop_completa", False)),
        ("Firmas", row.get("firmas_preop_completas", False)),
        ("Intraoperatoria", row.get("intraop_completa", False)),
        ("Postoperatoria", row.get("postop_completa", False)),
        ("PDF", bool(str(row.get("pdf_checklist", "")).strip())),
    ]
    cols = st.columns(len(labels))
    for col, (label, done) in zip(cols, labels):
        with col:
            if done:
                st.success(label)
            else:
                st.info(label)


def current_case_key(case_id, is_draft):
    return f"draft_{case_id}" if is_draft else str(case_id)


def render_preop_step(case_id, row: pd.Series, current: pd.DataFrame, paths: dict, is_draft: bool):
    preop = from_json(row.get("datos_preop", ""))
    st.subheader("Paso 1, fase preoperatoria")

    key_suffix = current_case_key(case_id, is_draft)
    a1, a2 = st.columns(2)
    with a1:
        st.markdown("**1. Identificación del paciente**")
        identificacion_confirmada = st.checkbox("Identidad confirmada", value=preop.get("identificacion_confirmada", False), key=f"identificacion_confirmada_{key_suffix}")
        manilla_seguridad = st.checkbox("Manilla de seguridad verificada", value=preop.get("manilla_seguridad", False), key=f"manilla_seguridad_{key_suffix}")

        st.markdown("**2. Confirmación del procedimiento**")
        current_site = preop.get("sitio_quirurgico", "")
        sitio_quirurgico = st.selectbox(
            "Sitio de incisión / miembro",
            SITIOS_QUIRURGICOS,
            index=SITIOS_QUIRURGICOS.index(current_site) if current_site in SITIOS_QUIRURGICOS else 0,
            key=f"sitio_quirurgico_{key_suffix}",
        )
        sitio_especificado = st.text_input("Especifique sitio", value=preop.get("sitio_especificado", ""), key=f"sitio_especificado_{key_suffix}")
        procedimiento_confirmado = st.checkbox("Procedimiento y sitio confirmados", value=preop.get("procedimiento_confirmado", False), key=f"procedimiento_confirmado_{key_suffix}")

        st.markdown("**3. Consentimiento informado**")
        consentimiento_informado = st.checkbox("Consentimiento informado firmado y vigente", value=preop.get("consentimiento_informado", False), key=f"consentimiento_informado_{key_suffix}")

        st.markdown("**4. Revisión de historia clínica**")
        historia_clinica_revisada = st.checkbox("Historia clínica revisada", value=preop.get("historia_clinica_revisada", False), key=f"historia_clinica_revisada_{key_suffix}")

    with a2:
        st.markdown("**5. Alergias**")
        allergy_key = f"tiene_alergias_{key_suffix}"
        ss_init(allergy_key, preop.get("tiene_alergias", "No"))
        tiene_alergias = st.radio("¿Presenta alergias?", ["No", "Sí"], horizontal=True, key=allergy_key)
        detail_key = f"detalle_alergias_{key_suffix}"
        ss_init(detail_key, preop.get("detalle_alergias", ""))
        check_key = f"alergias_verificadas_{key_suffix}"
        ss_init(check_key, preop.get("alergias_verificadas", False))
        if tiene_alergias == "No":
            st.session_state[detail_key] = ""
            st.session_state[check_key] = True
        detalle_alergias = st.text_input("Especifique las alergias identificadas", disabled=(tiene_alergias == "No"), key=detail_key)
        alergias_verificadas = st.checkbox("Alergias verificadas", disabled=(tiene_alergias == "No"), key=check_key)

        st.markdown("**6. Ayuno adecuado**")
        ayuno_adecuado = st.checkbox("Ayuno adecuado confirmado", value=preop.get("ayuno_adecuado", False), key=f"ayuno_adecuado_{key_suffix}")

        st.markdown("**7. Preparación del sitio quirúrgico**")
        sitio_preparado = st.checkbox("Sitio quirúrgico preparado correctamente", value=preop.get("sitio_preparado", False), key=f"sitio_preparado_{key_suffix}")

        st.markdown("**8. Verificación del instrumental**")
        equipo_utilizado = st.text_input("Equipo utilizado", value=preop.get("equipo_utilizado", ""), key=f"equipo_utilizado_{key_suffix}")
        cantidad_instrumentos = st.number_input("Cantidad de instrumentos", min_value=0, step=1, value=int(preop.get("cantidad_instrumentos", 0) or 0), key=f"cantidad_instrumentos_{key_suffix}")

        stored_ester = preop.get("fecha_esterilizacion", str(date.today()))
        ester_key = f"fecha_esterilizacion_{key_suffix}"
        ss_init(ester_key, datetime.strptime(stored_ester, "%Y-%m-%d").date() if stored_ester else date.today())
        fecha_esterilizacion = st.date_input("Fecha de esterilización", key=ester_key)

        min_vencimiento = fecha_esterilizacion + timedelta(days=90)
        stored_venc = preop.get("fecha_vencimiento", str(min_vencimiento))
        venc_key = f"fecha_vencimiento_{key_suffix}"
        ss_init(venc_key, datetime.strptime(stored_venc, "%Y-%m-%d").date() if stored_venc else min_vencimiento)
        if st.session_state[venc_key] < min_vencimiento:
            st.session_state[venc_key] = min_vencimiento
        fecha_vencimiento = st.date_input("Fecha de vencimiento del equipo", min_value=min_vencimiento, key=venc_key)

        instrumental_verificado = st.checkbox("Instrumental verificado", value=preop.get("instrumental_verificado", False), key=f"instrumental_verificado_{key_suffix}")

    if st.button("Guardar fase preoperatoria", key=f"guardar_preop_{key_suffix}"):
        data_preop = {
            "fecha_cirugia": str(row.get("fecha_cirugia", "")),
            "identificacion_confirmada": identificacion_confirmada,
            "manilla_seguridad": manilla_seguridad,
            "sitio_quirurgico": sitio_quirurgico,
            "sitio_especificado": sitio_especificado.strip() if sitio_quirurgico == "Especifique" else "",
            "procedimiento_confirmado": procedimiento_confirmado,
            "consentimiento_informado": consentimiento_informado,
            "historia_clinica_revisada": historia_clinica_revisada,
            "tiene_alergias": tiene_alergias,
            "detalle_alergias": detalle_alergias.strip() if tiene_alergias == "Sí" else "",
            "alergias_verificadas": True if tiene_alergias == "No" else alergias_verificadas,
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
            save_case_changes(case_id, is_draft, current, {"datos_preop": to_json(data_preop), "preop_completa": True, "checklist_iniciado": True}, paths)
            set_pending_step(key_suffix, "Firmas")
            st.success("Fase preoperatoria completada.")
            st.rerun()


def render_signatures_step(case_id, row: pd.Series, current: pd.DataFrame, paths: dict, is_draft: bool):
    st.subheader("Paso 2, firmas de confirmación")
    st.caption("Estas firmas son obligatorias antes de habilitar la fase intraoperatoria.")
    key_suffix = current_case_key(case_id, is_draft)
    base_name = f"draft_{key_suffix}" if is_draft else key_suffix

    b1, b2 = st.columns(2)
    with b1:
        aux_path = os.path.join(paths["firmas_dir"], f"firma_aux_{base_name}.png")
        firma_aux = signature_widget("Aux. enfermería circulante en sala", f"aux_{key_suffix}", aux_path)
        instr_path = os.path.join(paths["firmas_dir"], f"firma_instr_{base_name}.png")
        firma_instr = signature_widget("Instrumentador/a QX de la sala", f"instr_{key_suffix}", instr_path)
    with b2:
        cir_path = os.path.join(paths["firmas_dir"], f"firma_cir_{base_name}.png")
        firma_cir = signature_widget("Cirujano/a", f"cir_{key_suffix}", cir_path)
        anes_path = os.path.join(paths["firmas_dir"], f"firma_anes_{base_name}.png")
        firma_anes = signature_widget("Anestesiólogo/a", f"anes_{key_suffix}", anes_path)

    if st.button("Confirmar firmas preoperatorias", key=f"confirmar_firmas_{key_suffix}"):
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
            save_case_changes(
                case_id,
                is_draft,
                current,
                {
                    "firma_aux_circulante": firma_aux,
                    "firma_instrumentador": firma_instr,
                    "firma_cirujano": firma_cir,
                    "firma_anestesiologo": firma_anes,
                    "firmas_preop_completas": True,
                },
                paths,
            )
            set_pending_step(key_suffix, "Intraoperatoria")
            st.success("Firmas confirmadas. Ya puedes avanzar a la fase intraoperatoria.")
            st.rerun()


def render_intraop_step(case_id, row: pd.Series, current: pd.DataFrame, paths: dict, is_draft: bool):
    intraop = from_json(row.get("datos_intraop", ""))
    st.subheader("Paso 3, fase intraoperatoria")
    key_suffix = current_case_key(case_id, is_draft)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**1. Esterilidad del campo**")
        esterilidad_campo = st.checkbox("Esterilidad del campo confirmada", value=intraop.get("esterilidad_campo", False), key=f"esterilidad_campo_{key_suffix}")
        st.markdown("**2. Conteo de gasas y compresas**")
        gasas_inicio = st.number_input("Gasas al inicio", min_value=0, step=1, value=int(intraop.get("gasas_inicio", 0) or 0), key=f"gasas_inicio_{key_suffix}")
        gasas_cierre = st.number_input("Gasas al cierre", min_value=0, step=1, value=int(intraop.get("gasas_cierre", 0) or 0), key=f"gasas_cierre_{key_suffix}")
        compresas_inicio = st.number_input("Compresas al inicio", min_value=0, step=1, value=int(intraop.get("compresas_inicio", 0) or 0), key=f"compresas_inicio_{key_suffix}")
        compresas_cierre = st.number_input("Compresas al cierre", min_value=0, step=1, value=int(intraop.get("compresas_cierre", 0) or 0), key=f"compresas_cierre_{key_suffix}")
        conteo_correcto = st.checkbox("Conteo correcto confirmado", value=intraop.get("conteo_correcto", False), key=f"conteo_correcto_{key_suffix}")
        st.markdown("**3. Posición del paciente**")
        current_position = intraop.get("posicion_paciente", "")
        posicion_paciente = st.selectbox("Posición del paciente", POSICIONES_PACIENTE, index=POSICIONES_PACIENTE.index(current_position) if current_position in POSICIONES_PACIENTE else 0, key=f"posicion_paciente_{key_suffix}")
        posicion_confirmada = st.checkbox("Posición confirmada", value=intraop.get("posicion_confirmada", False), key=f"posicion_confirmada_{key_suffix}")

    with c2:
        st.markdown("**4. Medicación administrada**")
        medicacion_tipo = st.text_input("Tipo de medicamento", value=intraop.get("medicacion_tipo", ""), key=f"medicacion_tipo_{key_suffix}")
        medicacion_dosis = st.text_input("Dosis", value=intraop.get("medicacion_dosis", ""), key=f"medicacion_dosis_{key_suffix}")
        medicacion_registrada = st.checkbox("Medicación registrada", value=intraop.get("medicacion_registrada", False), key=f"medicacion_registrada_{key_suffix}")
        st.markdown("**5. Funcionamiento de equipos**")
        equipos_funcionando = st.checkbox("Equipos biomédicos y quirúrgicos funcionando", value=intraop.get("equipos_funcionando", False), key=f"equipos_funcionando_{key_suffix}")
        st.markdown("**6. Control del tiempo quirúrgico**")
        hora_inicio = st.time_input("Hora de inicio", value=datetime.strptime(intraop.get("hora_inicio", "08:00"), "%H:%M").time(), key=f"hora_inicio_{key_suffix}")
        hora_fin = st.time_input("Hora final", value=datetime.strptime(intraop.get("hora_fin", "09:00"), "%H:%M").time(), key=f"hora_fin_{key_suffix}")
        tiempo_registrado = st.checkbox("Tiempo quirúrgico registrado", value=intraop.get("tiempo_registrado", False), key=f"tiempo_registrado_{key_suffix}")
        st.markdown("**7. Registro de incidencias**")
        incidencias_key = f"hubo_incidencias_{key_suffix}"
        ss_init(incidencias_key, intraop.get("hubo_incidencias", "No"))
        hubo_incidencias = st.radio("¿Hubo incidencias?", ["No", "Sí"], horizontal=True, key=incidencias_key)
        detail_inc_key = f"detalle_incidencias_{key_suffix}"
        ss_init(detail_inc_key, intraop.get("detalle_incidencias", ""))
        inc_check_key = f"incidencias_registradas_{key_suffix}"
        ss_init(inc_check_key, intraop.get("incidencias_registradas", False))
        if hubo_incidencias == "No":
            st.session_state[detail_inc_key] = ""
            st.session_state[inc_check_key] = True
        detalle_incidencias = st.text_area("Detalle de incidencias", height=100, disabled=(hubo_incidencias == "No"), key=detail_inc_key)
        incidencias_registradas = st.checkbox("Incidencias registradas", disabled=(hubo_incidencias == "No"), key=inc_check_key)

    if st.button("Guardar fase intraoperatoria", key=f"guardar_intra_{key_suffix}"):
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
            "incidencias_registradas": True if hubo_incidencias == "No" else incidencias_registradas,
        }
        errors = validate_intraop(data_intra)
        if errors:
            show_errors(errors)
        else:
            save_case_changes(case_id, is_draft, current, {"datos_intraop": to_json(data_intra), "intraop_completa": True}, paths)
            set_pending_step(key_suffix, "Postoperatoria")
            st.success("Fase intraoperatoria completada.")
            st.rerun()


def render_postop_step(case_id, row: pd.Series, current: pd.DataFrame, paths: dict, is_draft: bool):
    postop = from_json(row.get("datos_postop", ""))
    st.subheader("Paso 4, fase postoperatoria")
    key_suffix = current_case_key(case_id, is_draft)
    indicaciones_ok = st.checkbox("1. Indicaciones postoperatorias verificadas", value=postop.get("indicaciones_ok", False), key=f"indicaciones_ok_{key_suffix}")
    comunicacion_recuperacion_ok = st.checkbox("2. Comunicación con recuperación realizada", value=postop.get("comunicacion_recuperacion_ok", False), key=f"comunicacion_recuperacion_ok_{key_suffix}")
    registro_medicamentos_ok = st.checkbox("3. Registro de medicamentos realizado", value=postop.get("registro_medicamentos_ok", False), key=f"registro_medicamentos_ok_{key_suffix}")
    drenajes_ok = st.checkbox("4. Verificación de drenajes y sondas realizada", value=postop.get("drenajes_ok", False), key=f"drenajes_ok_{key_suffix}")
    dolor_ok = st.checkbox("5. Control del dolor realizado", value=postop.get("dolor_ok", False), key=f"dolor_ok_{key_suffix}")
    conciencia_ok = st.checkbox("6. Control de conciencia realizado", value=postop.get("conciencia_ok", False), key=f"conciencia_ok_{key_suffix}")
    signos_vitales = st.text_area("7. Signos vitales", value=postop.get("signos_vitales", ""), height=100, key=f"signos_vitales_{key_suffix}")
    signos_ok = st.checkbox("Signos vitales confirmados", value=postop.get("signos_ok", False), key=f"signos_ok_{key_suffix}")

    if st.button("Guardar fase postoperatoria", key=f"guardar_post_{key_suffix}"):
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
            save_case_changes(case_id, is_draft, current, {"datos_postop": to_json(data_post), "postop_completa": True}, paths)
            set_pending_step(key_suffix, "PDF")
            st.success("Fase postoperatoria completada.")
            st.rerun()


def render_pdf_step(case_id, row: pd.Series, current: pd.DataFrame, paths: dict, is_draft: bool):
    key_suffix = current_case_key(case_id, is_draft)
    st.subheader("Paso 5, exportar PDF")
    st.success("Checklist completo. Ya puedes exportar el PDF.")
    if row.get("fecha_pdf_checklist", ""):
        st.caption(f"Último PDF generado: {row['fecha_pdf_checklist']}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Generar y archivar PDF", key=f"generar_pdf_{key_suffix}"):
            if is_draft:
                real_id = finalize_draft_to_cirugia(paths)
                current = load_cirugias(paths["cirugias"])
                final_row = current[current["id"] == real_id].iloc[0]
                pdf_path = export_pdf(final_row, paths["pdfs_dir"], paths["logo"])
                current = update_cirugia(current, real_id, {"pdf_checklist": pdf_path, "fecha_pdf_checklist": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                save_cirugias(current, paths["cirugias"])
                updated_row = current[current["id"] == real_id].iloc[0]
                upsert_checklist_historia(paths["historia"], updated_row, pdf_path)
                clear_draft()
                st.session_state["cirugia_activa_id"] = None
                st.session_state.pop(f"step_cirugia_{key_suffix}", None)
                st.success("PDF generado, cirugía archivada y retirada de la lista activa.")
                st.rerun()
            else:
                pdf_path = export_pdf(row, paths["pdfs_dir"], paths["logo"])
                current = load_cirugias(paths["cirugias"])
                current = update_cirugia(current, int(case_id), {"pdf_checklist": pdf_path, "fecha_pdf_checklist": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                save_cirugias(current, paths["cirugias"])
                updated_row = current[current["id"] == int(case_id)].iloc[0]
                upsert_checklist_historia(paths["historia"], updated_row, pdf_path)
                st.session_state["cirugia_activa_id"] = None
                st.session_state.pop(f"step_cirugia_{key_suffix}", None)
                st.success("PDF generado, archivado y retirado de la lista activa.")
                st.rerun()
    with col2:
        existing_pdf = str(row.get("pdf_checklist", ""))
        if existing_pdf and os.path.exists(existing_pdf):
            with open(existing_pdf, "rb") as file:
                st.download_button(
                    label="📥 Descargar último PDF",
                    data=file,
                    file_name=os.path.basename(existing_pdf),
                    mime="application/pdf",
                    key=f"descarga_pdf_{key_suffix}",
                )
        else:
            st.info("Todavía no has archivado un PDF de esta cirugía.")


def build_active_cases(cirugias: pd.DataFrame):
    activos = cirugias[cirugias["pdf_checklist"].astype(str).str.strip() == ""].copy()
    return activos.sort_values(by=["fecha_cirugia", "id"], ascending=[False, False]) if not activos.empty else activos


def render_cirugia(data_dir: str = "data", assets_dir: str = "assets"):
    paths = get_paths(data_dir, assets_dir)
    cirugias = load_cirugias(paths["cirugias"])
    st.title("🏥 Cirugía Segura")

    tab_ingreso, tab_checklist = st.tabs(["1. Ingreso del paciente", "2. Checklist por fases"])

    with tab_ingreso:
        st.subheader("Ingreso del paciente")
        prefill_key = "cirugia_prefill"
        if prefill_key not in st.session_state:
            st.session_state[prefill_key] = {
                "nombre_paciente": "",
                "numero_documento": "",
                "institucion": "",
                "tipo_documento": "",
                "fecha_nacimiento": "",
                "sexo": "",
            }

        apply_widget_reset("cirugia_busqueda_documento")
        lookup_col1, lookup_col2, lookup_col3 = st.columns([2, 1, 1])
        with lookup_col1:
            documento_busqueda = st.text_input("Cédula del paciente existente", key="cirugia_busqueda_documento")
        with lookup_col2:
            buscar_paciente = st.button("Buscar paciente", key="buscar_paciente_cirugia")
        with lookup_col3:
            limpiar_prefill = st.button("Limpiar datos", key="limpiar_prefill_cirugia")

        if buscar_paciente:
            paciente = find_paciente_by_documento(paths, documento_busqueda)
            if paciente:
                st.session_state[prefill_key] = paciente
                st.success("Paciente encontrado. Se cargaron sus datos.")
                st.rerun()
            else:
                alert_warning("No se encontró un paciente con ese documento.")

        if limpiar_prefill:
            st.session_state[prefill_key] = {
                "nombre_paciente": "",
                "numero_documento": "",
                "institucion": "",
                "tipo_documento": "",
                "fecha_nacimiento": "",
                "sexo": "",
            }
            reset_widget_on_next_run("cirugia_busqueda_documento")
            clear_draft()
            st.success("Datos limpiados.")
            st.rerun()

        draft = get_draft()
        base_data = draft if draft_has_data() else st.session_state[prefill_key]
        fecha_nac_default = date(2000, 1, 1)
        try:
            if str(base_data.get("fecha_nacimiento", "")).strip():
                fecha_nac_default = datetime.strptime(str(base_data.get("fecha_nacimiento", "")), "%Y-%m-%d").date()
        except Exception:
            fecha_nac_default = date(2000, 1, 1)

        with st.form("form_ingreso_cirugia"):
            c1, c2, c3 = st.columns(3)
            with c1:
                req_label("Nombre del paciente")
                nombre_paciente = st.text_input("nombre_paciente", value=str(base_data.get("nombre_paciente", "")), label_visibility="collapsed")
            with c2:
                req_label("No. de documento")
                numero_documento = st.text_input("numero_documento", value=str(base_data.get("numero_documento", "")), label_visibility="collapsed")
            with c3:
                req_label("Institución")
                institucion = st.text_input("institucion", value=str(base_data.get("institucion", "")), label_visibility="collapsed")

            c4, c5, c6, c7, c8 = st.columns(5)
            with c4:
                req_label("Tipo de documento")
                tipo_base = str(base_data.get("tipo_documento", TIPOS_DOCUMENTO[0]))
                tipo_documento = st.selectbox("tipo_documento", TIPOS_DOCUMENTO, index=TIPOS_DOCUMENTO.index(tipo_base) if tipo_base in TIPOS_DOCUMENTO else 0, label_visibility="collapsed")
            with c5:
                req_label("Fecha de nacimiento")
                fecha_nacimiento = st.date_input("fecha_nacimiento", value=fecha_nac_default, label_visibility="collapsed")
            with c6:
                req_label("Sexo")
                sexo_base = str(base_data.get("sexo", ""))
                sexo = st.selectbox("sexo", SEXOS, index=SEXOS.index(sexo_base) if sexo_base in SEXOS else 0, label_visibility="collapsed")
            with c7:
                req_label("Edad")
                edad_calculada = calculate_age(fecha_nacimiento)
                edad = st.number_input("edad", min_value=0, max_value=120, step=1, value=int(base_data.get("edad", edad_calculada) or edad_calculada), label_visibility="collapsed")
            with c8:
                req_label("Fecha cirugía")
                fecha_cirugia_base = str(base_data.get("fecha_cirugia", str(date.today())))
                try:
                    fecha_cirugia_default = datetime.strptime(fecha_cirugia_base, "%Y-%m-%d").date()
                except Exception:
                    fecha_cirugia_default = date.today()
                fecha_cirugia = st.date_input("fecha_cirugia", value=fecha_cirugia_default, label_visibility="collapsed")

            req_label("Procedimiento")
            procedimiento = st.text_input("procedimiento", value=str(base_data.get("procedimiento", "")), label_visibility="collapsed")
            guardar_ingreso = st.form_submit_button("Guardar datos para iniciar checklist")

            if guardar_ingreso:
                errors = []
                if not nombre_paciente.strip():
                    errors.append("El nombre del paciente es obligatorio.")
                if not numero_documento.strip():
                    errors.append("El número de documento es obligatorio.")
                if not institucion.strip():
                    errors.append("La institución es obligatoria.")
                if not sexo.strip():
                    errors.append("El sexo es obligatorio.")
                if int(edad) <= 0:
                    errors.append("La edad debe ser mayor que cero.")
                if not procedimiento.strip():
                    errors.append("El procedimiento es obligatorio.")
                if errors:
                    show_errors(errors)
                else:
                    save_draft({
                        **get_draft(),
                        "nombre_paciente": nombre_paciente.strip(),
                        "numero_documento": normalize_document(numero_documento),
                        "institucion": institucion.strip(),
                        "tipo_documento": tipo_documento,
                        "fecha_nacimiento": str(fecha_nacimiento),
                        "sexo": sexo,
                        "edad": int(edad),
                        "fecha_cirugia": str(fecha_cirugia),
                        "procedimiento": procedimiento.strip(),
                        "checklist_iniciado": True,
                    })
                    st.session_state["cirugia_modo_borrador"] = True
                    st.session_state["cirugia_activa_id"] = None
                    st.success("Datos guardados. Continúa con el checklist por fases.")
                    st.rerun()

        activos = build_active_cases(cirugias)
        if not activos.empty:
            st.divider()
            st.subheader("Cirugías activas, aún no archivadas")
            st.dataframe(
                activos[["id", "nombre_paciente", "numero_documento", "fecha_cirugia", "procedimiento", "preop_completa", "firmas_preop_completas", "intraop_completa", "postop_completa"]],
                use_container_width=True,
            )

    with tab_checklist:
        activos = build_active_cases(load_cirugias(paths["cirugias"]))
        draft_mode = st.session_state.get("cirugia_modo_borrador", False) and draft_has_data()
        options = []
        labels = {}
        if draft_mode:
            draft = get_draft()
            draft_option = f"draft::{draft['draft_id']}"
            options.append(draft_option)
            labels[draft_option] = f"Borrador actual | {draft.get('nombre_paciente','')} | {draft.get('procedimiento','')}"
        for _, row in activos.iterrows():
            opt = f"row::{int(row['id'])}"
            options.append(opt)
            labels[opt] = f"Cirugía #{int(row['id'])} | {row['nombre_paciente']} | {row['procedimiento']}"

        if not options:
            alert_warning("No hay checklists activas. Ingresa un paciente y completa una nueva checklist.")
            return

        default_opt = options[0]
        saved_opt = st.session_state.get("cirugia_case_option")
        if saved_opt in options:
            default_opt = saved_opt
        selected_option = st.selectbox("Seleccione la checklist activa", options=options, index=options.index(default_opt), format_func=lambda x: labels.get(x, x))
        st.session_state["cirugia_case_option"] = selected_option

        is_draft = selected_option.startswith("draft::")
        if is_draft:
            row = draft_as_series()
            case_id = row["draft_id"]
        else:
            case_id = int(selected_option.split("::", 1)[1])
            current_df = load_cirugias(paths["cirugias"])
            row = current_df[current_df["id"] == case_id].iloc[0]

        st.info(
            f"Paciente: {row.get('nombre_paciente', '')} | Documento: {row.get('tipo_documento', '')} {row.get('numero_documento', '')} | "
            f"Sexo: {row.get('sexo', '')} | Edad: {row.get('edad', '')} | Fecha cirugía: {row.get('fecha_cirugia', '')} | Procedimiento: {row.get('procedimiento', '')}"
        )
        render_step_status(row)

        enabled_steps = get_enabled_steps(row)
        recommended_step = get_recommended_step(row)
        case_key = current_case_key(case_id, is_draft)
        step_key = f"step_cirugia_{case_key}"
        pending_key = f"pending_step_cirugia_{case_key}"
        pending_step = st.session_state.pop(pending_key, None)
        if pending_step in enabled_steps:
            st.session_state[step_key] = pending_step
        elif st.session_state.get(step_key) not in enabled_steps:
            st.session_state[step_key] = recommended_step

        st.divider()
        st.caption("Cada fase se muestra en un frame diferente. La siguiente se habilita solo cuando la anterior se guarda correctamente.")
        selected_step = st.radio("Frame activo", options=enabled_steps, horizontal=True, key=step_key)

        current_df = load_cirugias(paths["cirugias"]) if not is_draft else pd.DataFrame(columns=CIRUGIA_COLUMNS)
        row = draft_as_series() if is_draft else current_df[current_df["id"] == case_id].iloc[0]

        st.divider()
        if selected_step == "Preoperatoria":
            render_preop_step(case_id, row, current_df, paths, is_draft)
        elif selected_step == "Firmas":
            if not row.get("preop_completa", False):
                alert_warning("Debes completar la fase preoperatoria para habilitar las firmas.")
            else:
                render_signatures_step(case_id, row, current_df, paths, is_draft)
        elif selected_step == "Intraoperatoria":
            if not row.get("firmas_preop_completas", False):
                alert_warning("Debes completar la fase preoperatoria y las firmas para habilitar la fase intraoperatoria.")
            else:
                render_intraop_step(case_id, row, current_df, paths, is_draft)
        elif selected_step == "Postoperatoria":
            if not row.get("intraop_completa", False):
                alert_warning("Debes completar la fase intraoperatoria para habilitar la fase postoperatoria.")
            else:
                render_postop_step(case_id, row, current_df, paths, is_draft)
        elif selected_step == "PDF":
            if not (row.get("preop_completa", False) and row.get("firmas_preop_completas", False) and row.get("intraop_completa", False) and row.get("postop_completa", False)):
                alert_warning("Debes completar todas las fases y las firmas para habilitar la exportación del PDF.")
            else:
                render_pdf_step(case_id, row, current_df, paths, is_draft)


if __name__ == "__main__":
    render_cirugia()
