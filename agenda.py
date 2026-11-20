"""Agenda quirúrgica: calendario, programación de cirugías y descargas.

Acceso para Administrador y Enfermería (jefa de enfermería).
Persistencia en data/programacion.csv.
"""
import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from navegacion import botones_nav
import db
from parametros import opciones as opciones_param
from esterilizacion import cargar as cargar_tabla, sets_vencidos

COLUMNAS = ["id", "fecha", "hora", "paciente", "documento", "procedimiento", "cirujano",
            "quirofano", "estado", "materiales", "observaciones", "duracion_min", "programada_por", "modificado", "usuario"]
ESTADOS = ["Programada", "Confirmada", "En curso", "Realizada", "Cancelada"]
ROLES_AGENDA = {"Administrador", "Enfermería", "Enfermeria"}


def ruta(data_dir="data"):
    return os.path.join(data_dir, "programacion.csv")


def cargar(data_dir="data"):
    df = db.leer("programacion")
    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = ""
    return df[COLUMNAS].copy()


def guardar(df, data_dir="data"):
    db.guardar("programacion", df[COLUMNAS])


def _ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _usuario():
    return str(st.session_state.get("usuario", "Sistema"))


def _pacientes(data_dir):
    path = os.path.join(data_dir, "pacientes.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=["nombre", "numero_documento", "institucion"])
    df = pd.read_csv(path, dtype=str).fillna("")
    return df


def _mes_actual():
    return st.session_state.get("agenda_mes", date.today().replace(day=1))


def _cambiar_mes(delta):
    m = _mes_actual()
    y = m.year + (m.month - 1 + delta) // 12
    mo = (m.month - 1 + delta) % 12 + 1
    st.session_state["agenda_mes"] = date(y, mo, 1)


DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _items_dia(dia, por_dia):
    return sorted(por_dia.get(dia, []), key=lambda r: str(r.get("hora", "")))


def _tarjeta_evento(r):
    est = str(r.get("estado", ""))
    borde = {"Cancelada": "#c0392b", "Realizada": "#1e8449", "En curso": "#2471a3"}.get(est, "#123b6d")
    return ("<div style='background:#eef4fb;border-left:4px solid " + borde + ";border-radius:5px;"
            "padding:3px 7px;margin:3px 0;font-size:11.5px;line-height:1.35'>"
            "<b>" + str(r.get("hora", "--:--")) + "</b> " + str(r.get("paciente", ""))[:22] + "<br>"
            "<span style='color:#5a6a7d'>" + str(r.get("procedimiento", ""))[:30]
            + (" · " + str(r.get("cirujano")) if str(r.get("cirujano", "")).strip() else "")
            + (" · " + str(r.get("duracion_min")) + " min" if str(r.get("duracion_min", "")).strip() else "")
            + "</span></div>")


def _grid_mes(df, por_dia, sets_ok):
    ini = _mes_actual()
    ultimo = (ini.replace(day=28) + timedelta(days=7)).replace(day=1) - timedelta(days=1)
    dias_mes = (ultimo - ini).days + 1
    offset = ini.weekday()
    celdas = [None] * offset + [ini + timedelta(days=i) for i in range(dias_mes)]
    while len(celdas) % 7:
        celdas.append(None)
    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
        st.button("◀ Mes anterior", on_click=_cambiar_mes, args=(-1,), width="stretch")
    with nav2:
        st.subheader(ini.strftime("%B %Y").capitalize())
    with nav3:
        st.button("Mes siguiente ▶", on_click=_cambiar_mes, args=(1,), width="stretch")
    st.caption("Sets estériles vigentes en central: **" + str(sets_ok) + "** · Material usado se gestiona en Central de Esterilización (admin).")
    seleccion = st.session_state.get("agenda_dia_sel")
    for semana in range(0, len(celdas), 7):
        cols = st.columns(7)
        for j, dia in enumerate(celdas[semana:semana + 7]):
            with cols[j]:
                if dia is None:
                    st.write("")
                    continue
                items = _items_dia(dia, por_dia)
                if st.button("**" + str(dia.day) + "**" + (" · " + str(len(items)) if items else ""), key="dia_" + str(dia),
                             width="stretch", type="primary" if seleccion == dia else "secondary"):
                    st.session_state["agenda_dia_sel"] = dia
                    st.rerun()
                cont = "".join(_tarjeta_evento(r) for r in items[:3])
                if len(items) > 3:
                    cont += "<div style='font-size:10px;color:#7a8a9d'>+" + str(len(items) - 3) + " más</div>"
                if cont:
                    st.markdown(cont, unsafe_allow_html=True)


def _grid_semana(df, por_dia, sets_ok):
    base = st.session_state.get("agenda_semana") or date.today()
    lunes = base - timedelta(days=base.weekday())
    st.session_state["agenda_semana"] = lunes

    def _semana_ant():
        st.session_state["agenda_semana"] = lunes - timedelta(days=7)

    def _semana_sig():
        st.session_state["agenda_semana"] = lunes + timedelta(days=7)

    nav1, nav2, nav3 = st.columns([1, 4, 1])
    with nav1:
        st.button("◀ Semana anterior", on_click=_semana_ant, width="stretch")
    with nav2:
        st.subheader("Semana del " + lunes.strftime("%d/%m") + " al " + (lunes + timedelta(days=6)).strftime("%d/%m/%Y"))
    with nav3:
        st.button("Semana siguiente ▶", on_click=_semana_sig, width="stretch")
    st.caption("Sets estériles vigentes en central: **" + str(sets_ok) + "**")

    dias = [lunes + timedelta(days=i) for i in range(7)]
    todos_horas = sorted({int(str(r.get("hora", ""))[:2]) for items in por_dia.values() for r in items
                          if str(r.get("hora", ""))[:2].isdigit()} | set(range(7, 20)))
    seleccion = st.session_state.get("agenda_dia_sel")
    hdr = st.columns(8)
    with hdr[0]:
        st.markdown("**Hora**")
    for j, dia in enumerate(dias):
        with hdr[j + 1]:
            if st.button(DIAS[j] + " " + str(dia.day) + "/" + str(dia.month), key="sem_dia_" + str(dia), width="stretch",
                         type="primary" if seleccion == dia else "secondary"):
                st.session_state["agenda_dia_sel"] = dia
                st.rerun()
    contenedor = st.container(border=True)
    for h in todos_horas:
        fila = contenedor.columns(8)
        with fila[0]:
            st.markdown("<div style='font-size:11px;color:#5a6a7d;padding-top:6px'>" + "%02d:00" % h + "</div>", unsafe_allow_html=True)
        for j, dia in enumerate(dias):
            with fila[j + 1]:
                evs = [r for r in _items_dia(dia, por_dia)
                       if str(r.get("hora", ""))[:2].isdigit() and int(str(r["hora"])[:2]) == h]
                if evs:
                    st.markdown("".join(_tarjeta_evento(r) for r in evs), unsafe_allow_html=True)
    fuera = [(dia, r) for dia in dias for r in _items_dia(dia, por_dia)
             if not (str(r.get("hora", ""))[:2].isdigit() and int(str(r["hora"])[:2]) in todos_horas)]
    if fuera:
        st.caption("Fuera del horario visible: " + "; ".join(
            DIAS[dias.index(d)] + " " + str(r.get("hora", "?")) + " " + str(r.get("paciente", ""))[:20] for d, r in fuera))


def _detalle_dia(df, data_dir):
    sel = st.session_state.get("agenda_dia_sel")
    st.divider()
    if not sel:
        st.info("Selecciona un día para ver o gestionar sus cirugías.")
        return
    st.subheader("Cirugías del " + sel.strftime("%d/%m/%Y"))
    del_dia = df[pd.to_datetime(df["fecha"], errors="coerce").dt.date == sel] if not df.empty else df
    if del_dia.empty:
        st.success("No hay cirugías programadas este día.")
        return
    vista = del_dia[["id", "hora", "paciente", "procedimiento", "cirujano", "quirofano", "estado", "duracion_min", "programada_por"]].copy()
    st.dataframe(vista, width="stretch", hide_index=True)
    for _, r in del_dia.iterrows():
        with st.expander("#" + str(r["id"]) + " " + str(r["hora"]) + " — " + str(r["paciente"]) + " (" + str(r["estado"]) + ")"):
            dur = str(r["duracion_min"]).strip()
            st.write("**Documento:** " + str(r["documento"]) + "  |  **Procedimiento:** " + str(r["procedimiento"]))
            st.write("**Cirujano/a:** " + str(r["cirujano"]) + "  |  **Quirófano:** " + str(r["quirofano"]) + "  |  **Duración:** " + (dur + " min" if dur else "—"))
            st.write("**Programada por:** " + str(r["programada_por"] or "—") + "  |  **Último cambio:** " + str(r["modificado"] or "—"))
            if str(r["materiales"]).strip():
                st.write("**Materiales:** " + str(r["materiales"]))
            if str(r["observaciones"]).strip():
                st.write("**Observaciones:** " + str(r["observaciones"]))
            ops = {"Confirmar": "Confirmada", "Iniciar": "En curso", "Realizada": "Realizada", "Cancelar": "Cancelada"}
            cols = st.columns(4)
            for col, (txt, est) in zip(cols, ops.items()):
                if col.button(txt, key="op_" + str(r["id"]) + "_" + txt, disabled=str(r["estado"]) == est):
                    idx = df.index[df["id"] == r["id"]][0]
                    df.loc[idx, "estado"] = est
                    df.loc[idx, "modificado"] = _ahora()
                    df.loc[idx, "usuario"] = _usuario()
                    guardar(df, data_dir)
                    st.rerun()


def _calendario(df, data_dir):
    por_dia = {}
    if not df.empty:
        for _, r in df.iterrows():
            f = pd.to_datetime(r["fecha"], errors="coerce")
            if pd.notna(f):
                por_dia.setdefault(f.date(), []).append(r)
    instrumental = cargar_tabla(data_dir, "instrumental")
    sets_ok = int(((instrumental["estado"] == "Esterilizado") & ~sets_vencidos(instrumental)).sum()) if not instrumental.empty else 0

    vista = st.session_state.get("agenda_vista", "Mes")
    t1, t2 = st.columns(2)
    with t1:
        if st.button("🗓️ Vista mes", width="stretch", type="primary" if vista == "Mes" else "secondary"):
            st.session_state["agenda_vista"] = "Mes"
            st.rerun()
    with t2:
        if st.button("🕐 Vista semana por horas", width="stretch", type="primary" if vista == "Semana" else "secondary"):
            st.session_state["agenda_vista"] = "Semana"
            st.rerun()

    if vista == "Semana":
        _grid_semana(df, por_dia, sets_ok)
    else:
        _grid_mes(df, por_dia, sets_ok)
    _detalle_dia(df, data_dir)


def _programar(df, data_dir):
    st.subheader("Programar cirugía")
    pacs = _pacientes(data_dir)
    nombres = sorted(set(pacs.get("nombre", pd.Series(dtype=str)).astype(str)) - {""}) if not pacs.empty else []
    docs = dict(zip(pacs.get("nombre", pd.Series(dtype=str)), pacs.get("numero_documento", pd.Series(dtype=str)))) if not pacs.empty else {}
    with st.form("form_programar"):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", value=date.today())
            hora = st.time_input("Hora inicio", value=datetime.now().time().replace(second=0, microsecond=0))
            duracion = st.selectbox("Duración", [30, 45, 60, 90, 120, 150, 180], index=2, format_func=lambda m: f"{m} min")
        with c2:
            paciente = st.selectbox("Paciente", ["— Nuevo / escribir —"] + nombres) if nombres else st.text_input("Paciente")
            if nombres and paciente == "— Nuevo / escribir —":
                paciente = st.text_input("Nombre del paciente")
            documento = st.text_input("Documento", value=str(docs.get(paciente, "")) if paciente in docs else "")
        with c3:
            procedimiento = st.text_input("Procedimiento")
            cirujano = st.selectbox("Cirujano/a", opciones_param("cirujano") or ["—"])
            quiro = st.selectbox("Quirófano", opciones_param("quirofano") or ["Quirófano 1", "Quirófano 2"])
            materiales = st.text_area("Materiales / insumos requeridos", height=68)
            observaciones = st.text_input("Observaciones")
        if st.form_submit_button("📅 Programar", type="primary"):
            if not str(paciente).strip() or not procedimiento.strip():
                st.error("Paciente y procedimiento son obligatorios.")
            else:
                nuevo_id = int(df["id"].max() + 1) if not df.empty and str(df["id"].max()).isdigit() else 1
                fila = pd.DataFrame([[nuevo_id, str(fecha), hora.strftime("%H:%M"), paciente.strip().title(), documento.strip().upper(),
                                      procedimiento.strip().title(), cirujano if cirujano != "—" else "", quiro, "Programada",
                                      materiales.strip().capitalize(), observaciones.strip().capitalize(), str(duracion), _usuario(), _ahora(), _usuario()]], columns=COLUMNAS)
                guardar(pd.concat([df, fila], ignore_index=True), data_dir)
                st.session_state["agenda_dia_sel"] = fecha
                st.success("Cirugía programada.")
                st.rerun()


def _listado_y_descargas(df, data_dir):
    st.subheader("Programación")
    if df.empty:
        st.info("No hay cirugías programadas.")
        return
    f1, f2, f3 = st.columns(3)
    fechas = pd.to_datetime(df["fecha"], errors="coerce")
    ini = f1.date_input("Desde", value=date.today() - timedelta(days=30), key="lst_desde")
    fin = f2.date_input("Hasta", value=date.today() + timedelta(days=60), key="lst_hasta")
    estados = f3.multiselect("Estado", ESTADOS, default=["Programada", "Confirmada", "En curso"], key="lst_est")
    vista = df.copy()
    if estados:
        vista = vista[vista["estado"].isin(estados)]
    vista = vista[(fechas >= pd.Timestamp(ini)) & (fechas <= pd.Timestamp(fin))].sort_values(["fecha", "hora"])
    st.dataframe(vista[["fecha", "hora", "paciente", "documento", "procedimiento", "cirujano", "quirofano", "estado", "duracion_min", "programada_por", "materiales"]], width="stretch", hide_index=True)
    st.caption(f"{len(vista)} cirugías en el filtro.")

    st.divider()
    st.subheader("Descargas")

    def _xlsx(df, hoja):
        from io import BytesIO
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter
        wb = Workbook()
        ws = wb.active
        ws.title = hoja[:31]
        cols = list(df.columns)
        ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True)
        for _, r in df.iterrows():
            ws.append([r[c] for c in cols])
        for i, c in enumerate(cols, 1):
            ancho = max([len(str(c))] + [len(str(x)) for x in df[c].astype(str).head(200)])
            ws.column_dimensions[get_column_letter(i)].width = min(max(ancho + 2, 10), 45)
        ws.freeze_panes = "A2"
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    cols_prog = ["Fecha", "Hora", "Paciente", "Documento", "Procedimiento", "Cirujano/a", "Quirófano",
                 "Estado", "Duración (min)", "Programada por", "Materiales", "Observaciones"]
    prog_xlsx = vista.rename(columns={"fecha": "Fecha", "hora": "Hora", "paciente": "Paciente", "documento": "Documento",
                                       "procedimiento": "Procedimiento", "cirujano": "Cirujano/a", "quirofano": "Quirófano",
                                       "estado": "Estado", "duracion_min": "Duración (min)", "programada_por": "Programada por",
                                       "materiales": "Materiales", "observaciones": "Observaciones"})[cols_prog]
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("⬇️ Programación (Excel)", _xlsx(prog_xlsx, "Programación"),
                           "programacion.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    usuarios = pd.read_csv(os.path.join(data_dir, "usuarios.csv"), dtype=str).fillna("") if os.path.exists(os.path.join(data_dir, "usuarios.csv")) else pd.DataFrame(columns=["usuario", "rol"])
    usuarios = usuarios[["usuario", "rol"]].rename(columns={"usuario": "Usuario", "rol": "Rol"}) if not usuarios.empty else pd.DataFrame(columns=["Usuario", "Rol"])
    with d2:
        st.download_button("⬇️ Acceso del personal (Excel)", _xlsx(usuarios, "Personal"),
                           "personal.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    with st.expander("👥 Personal con acceso"):
        st.dataframe(usuarios, width="stretch", hide_index=True)


def render_agenda(data_dir="data", sidebar=None):
    st.title("📅 Agenda Quirúrgica")
    if st.session_state.get("rol") not in ROLES_AGENDA:
        st.error("Solo la jefa de enfermería o el administrador pueden gestionar la agenda.")
        return
    paneles = {"📅 Calendario": _calendario, "📝 Programar": _programar, "📋 Listado y descargas": _listado_y_descargas}
    panel = botones_nav(list(paneles), "panel_agenda", contenedor=sidebar or st.sidebar, titulo="Agenda")
    df = cargar(data_dir)
    paneles[panel](df, data_dir)
