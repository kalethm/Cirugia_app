from datetime import date, timedelta

import pandas as pd
import streamlit as st

from cirugia import load_cirugias, get_paths
from historia_clinica_paciente import checklist_completo, load_historia
from esterilizacion import cargar as cargar_tabla, sets_vencidos, sets_por_vencer, numeros
from navegacion import botones_nav
from parametros import opciones as opciones_param

MESES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
         7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}


def _meses_rango(inicio: date, fin: date):
    out, y, m = [], inicio.year, inicio.month
    while (y, m) <= (fin.year, fin.month):
        out.append((y, m))
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return out


def _por_mes(df, columna_fecha, meses):
    fechas = pd.to_datetime(df[columna_fecha], errors="coerce")
    claves = fechas.dt.year.astype(str) + "-" + fechas.dt.month.astype(str).str.zfill(2)
    conteo = claves.value_counts()
    return pd.DataFrame({"Mes": [f"{MESES[m]} {y}" for y, m in meses],
                         "Cantidad": [int(conteo.get(f"{y}-{m:02d}", 0)) for y, m in meses]})


def _conteo(col, etiqueta_vacia="Sin especificar"):
    valores = col.astype(str).str.strip().replace("", etiqueta_vacia).replace("nan", etiqueta_vacia)
    top = valores.value_counts()
    nombre = getattr(col, "name", None) or "Categoría"
    return pd.DataFrame({nombre: top.index, "Cantidad": top.values})


def _excel_bytes(resumen, graficas, detalle):
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    ws.append(["Indicador", "Valor"])
    for k, v in resumen:
        ws.append([k, v])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for nombre, df in graficas:
        s = wb.create_sheet(str(nombre)[:31])
        cols = list(df.columns)
        s.append(cols)
        for _, r in df.iterrows():
            s.append([r[c] for c in cols])
        for cell in s[1]:
            cell.font = Font(bold=True)
        if len(df):
            chart = BarChart()
            chart.type = "col"
            chart.title = str(nombre)
            chart.height, chart.width = 7, 14
            chart.add_data(Reference(s, min_col=2, min_row=1, max_row=len(df) + 1), titles_from_data=True)
            chart.set_categories(Reference(s, min_col=1, min_row=2, max_row=len(df) + 1))
            s.add_chart(chart, "D2")
    d = wb.create_sheet("Cirugías")
    d.append(list(detalle.columns))
    for _, r in detalle.iterrows():
        d.append([r[c] for c in detalle.columns])
    for cell in d[1]:
        cell.font = Font(bold=True)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _rango_fechas(clave="met_rango"):
    hoy = date.today()
    rango = st.date_input("Rango de fechas", value=(hoy - timedelta(days=365), hoy), key=clave)
    if isinstance(rango, tuple) and len(rango) == 2:
        ini, fin = rango
    else:
        ini = fin = rango
    return min(ini, fin), max(ini, fin)


def _multi(clave, etiqueta, valores):
    if not valores:
        return []
    return st.multiselect(etiqueta, valores, key=clave)


def _filtros_cirugia(cirugias):
    """Renderiza la barra de filtros y devuelve (df filtrado, meta)."""
    hoy = date.today()
    ini, fin = _rango_fechas()
    uni = sorted(set(x for x in cirugias["institucion"].astype(str).str.strip().unique() if x not in ("", "nan")) | set(opciones_param("institucion")))
    upro = sorted(set(x for x in cirugias["procedimiento"].astype(str).str.strip().unique() if x not in ("", "nan")) | set(opciones_param("procedimiento")))
    ucir = sorted(set(x for x in cirugias.get("cirujano", pd.Series(dtype=str)).astype(str).str.strip().unique() if x not in ("", "nan")) | set(opciones_param("cirujano")))
    usex = sorted(set(x for x in cirugias["sexo"].astype(str).str.strip().unique() if x not in ("", "nan")) | set(opciones_param("sexo")))
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        inst_sel = _multi("met_inst", "Institución", uni)
    with c2:
        proc_sel = _multi("met_proc", "Procedimiento", upro)
    with c3:
        cir_sel = _multi("met_cir", "Cirujano/a", ucir)
    with c4:
        sexo_sel = _multi("met_sexo", "Sexo", usex)
    with c5:
        if hasattr(st, "pills"):
            estado = st.pills("Checklist", ["Todos", "Completo", "Incompleto"], default="Todos", key="met_estado")
        else:
            estado = st.selectbox("Checklist", ["Todos", "Completo", "Incompleto"], key="met_estado")
    df = cirugias.copy()
    fechas = pd.to_datetime(df["fecha_cirugia"], errors="coerce").dt.normalize()
    df = df[(fechas >= pd.Timestamp(ini)) & (fechas <= pd.Timestamp(fin))]
    if inst_sel:
        df = df[df["institucion"].astype(str).str.strip().isin(inst_sel)]
    if proc_sel:
        df = df[df["procedimiento"].astype(str).str.strip().isin(proc_sel)]
    if cir_sel:
        df = df[df.get("cirujano", pd.Series("", index=df.index)).astype(str).str.strip().isin(cir_sel)]
    if sexo_sel:
        df = df[df["sexo"].astype(str).str.strip().isin(sexo_sel)]
    if estado != "Todos":
        comp = df.apply(checklist_completo, axis=1)
        df = df[comp == (estado == "Completo")]
    meses = _meses_rango(ini, fin)
    meta = {"ini": ini, "fin": fin, "meses": meses[-max(1, min(24, len(meses))):], "hoy": hoy, "estado": estado}
    return df, meta


def _central(data_dir, ini, fin):
    instrumental = cargar_tabla(data_dir, "instrumental")
    cargas = cargar_tabla(data_dir, "cargas")
    insumos = cargar_tabla(data_dir, "insumos")
    equipos = cargar_tabla(data_dir, "equipos")
    if not cargas.empty:
        fc = pd.to_datetime(cargas["fecha"], errors="coerce").dt.normalize()
        cargas = cargas[(fc >= pd.Timestamp(ini)) & (fc <= pd.Timestamp(fin))]
    return instrumental, cargas, insumos, equipos


def _kpis_cirugia(df, meta):
    fechas = pd.to_datetime(df["fecha_cirugia"], errors="coerce")
    completos = df.apply(checklist_completo, axis=1) if len(df) else pd.Series(dtype=bool)
    return {
        "mes": int((fechas.dt.to_period("M") == pd.Period(meta["hoy"], freq="M")).sum()),
        "anio": int((fechas.dt.year == meta["hoy"].year).sum()),
        "pct": round(100 * completos.mean()) if len(df) else 0,
    }


def _panel_resumen(data_dir):
    cirugias = load_cirugias(get_paths(data_dir, "assets")["cirugias"])
    if cirugias.empty:
        st.info("Todavía no hay cirugías registradas.")
        return
    df, meta = _filtros_cirugia(cirugias)
    st.caption(f"Mostrando {len(df)} de {len(cirugias)} cirugías con los filtros.")
    if df.empty:
        st.warning("Ninguna cirugía coincide con los filtros.")
        return
    instrumental, cargas, insumos, equipos = _central(data_dir, meta["ini"], meta["fin"])
    kp = _kpis_cirugia(df, meta)
    vencidos = int(sets_vencidos(instrumental).sum()) if not instrumental.empty else 0
    por_vencer = int(sets_por_vencer(instrumental).sum()) if not instrumental.empty else 0
    cuarentena = int((cargas["resultado"] == "En cuarentena").sum()) if not cargas.empty else 0
    bajo = int((numeros(insumos["stock"]) <= numeros(insumos["stock_minimo"])).sum()) if not insumos.empty else 0
    prox = pd.to_datetime(equipos["proximo_mantenimiento"], errors="coerce")
    mtto = int(((prox <= pd.Timestamp.now().normalize() + pd.Timedelta(days=15)) & (equipos["estado"] != "Fuera de servicio")).sum()) if not equipos.empty else 0
    sets_vig = int(((instrumental["estado"] == "Esterilizado") & ~sets_vencidos(instrumental)).sum()) if not instrumental.empty else 0
    c = st.columns(6)
    c[0].metric("Cirugías este mes", kp["mes"])
    c[1].metric("Cirugías este año", kp["anio"])
    c[2].metric("Checklists completos", f"{kp['pct']}%")
    c[3].metric("Sets estériles vigentes", sets_vig)
    c[4].metric("Cargas en cuarentena", cuarentena)
    c[5].metric("Alertas esterilización", vencidos + por_vencer + cuarentena + bajo + mtto)
    st.divider()
    st.markdown("**Alertas de esterilización**")
    for txt in [
        f"• {vencidos} sets vencidos" if vencidos else None,
        f"• {por_vencer} sets por vencer en 30 días" if por_vencer else None,
        f"• {cuarentena} cargas en cuarentena" if cuarentena else None,
        f"• {bajo} insumos bajo el mínimo" if bajo else None,
        f"• {mtto} equipos con mantenimiento próximo" if mtto else None,
    ]:
        if txt:
            st.markdown(txt)
    if not any([vencidos, por_vencer, cuarentena, bajo, mtto]):
        st.success("Sin alertas en la central de esterilización.")

    try:
        from agenda import cargar as cargar_prog
        prog = cargar_prog(data_dir)
        if not prog.empty:
            fp = pd.to_datetime(prog["fecha"], errors="coerce").dt.normalize()
            pv = prog[(fp >= pd.Timestamp(meta["ini"])) & (fp <= pd.Timestamp(meta["fin"]))]
            if not pv.empty:
                st.divider()
                st.markdown("**Agenda quirúrgica (rango filtrado)**")
                st.metric("Cirugías programadas", len(pv))
                g7, g8 = st.columns(2)
                with g7:
                    por_est = pv["estado"].value_counts()
                    st.bar_chart(pd.DataFrame({"Estado": por_est.index, "Cantidad": por_est.values}), x="Estado", y="Cantidad", width="stretch")
                with g8:
                    por_user = pv.get("programada_por", pd.Series("Sin dato", index=pv.index)).replace("", "Sin dato").value_counts()
                    st.bar_chart(pd.DataFrame({"Usuario": por_user.index, "Programadas": por_user.values}), x="Usuario", y="Programadas", width="stretch")
    except Exception:
        pass


def _panel_cirugia(data_dir):
    cirugias = load_cirugias(get_paths(data_dir, "assets")["cirugias"])
    if cirugias.empty:
        st.info("Sin cirugías registradas.")
        return
    df, meta = _filtros_cirugia(cirugias)
    if df.empty:
        st.warning("Ninguna cirugía coincide con los filtros.")
        return
    meses = meta["meses"]
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Cirugías por mes")
        st.bar_chart(_por_mes(df, "fecha_cirugia", meses), x="Mes", y="Cantidad", width="stretch")
    with g2:
        st.subheader("Procedimientos más frecuentes")
        st.bar_chart(_conteo(df["procedimiento"]).rename(columns={"procedimiento": "Procedimiento", "Cantidad": "Cirugías"}), x="Procedimiento", y="Cirugías", width="stretch")
    g3, g4 = st.columns(2)
    with g3:
        st.subheader("Instituciones")
        st.bar_chart(_conteo(df["institucion"]).rename(columns={"institucion": "Institución", "Cantidad": "Cirugías"}), x="Institución", y="Cirugías", width="stretch")
    with g4:
        st.subheader("Cirujanos")
        st.bar_chart(_conteo(df.get("cirujano", pd.Series(dtype=str))).rename(columns={"cirujano": "Cirujano/a", "Cantidad": "Cirugías"}), x="Cirujano/a", y="Cirugías", width="stretch")
    g5, g6 = st.columns(2)
    with g5:
        st.subheader("Sexo")
        st.bar_chart(_conteo(df["sexo"]).rename(columns={"sexo": "Sexo", "Cantidad": "Cirugías"}), x="Sexo", y="Cirugías", width="stretch")
    with g6:
        st.subheader("Edad promedio por procedimiento (top 8)")
        top = df["procedimiento"].astype(str).str.strip().replace("", "Sin especificar").value_counts().head(8).index
        prom = df[df["procedimiento"].astype(str).str.strip().isin(top)].groupby(df["procedimiento"].astype(str).str.strip().replace("", "Sin especificar"))["edad"].mean().round(1)
        st.bar_chart(pd.DataFrame({"Procedimiento": prom.index, "Edad prom.": prom.values}), x="Procedimiento", y="Edad prom.", width="stretch")


def _panel_checklist(data_dir):
    cirugias = load_cirugias(get_paths(data_dir, "assets")["cirugias"])
    if cirugias.empty:
        st.info("Sin cirugías registradas.")
        return
    df, meta = _filtros_cirugia(cirugias)
    if df.empty:
        st.warning("Ninguna cirugía coincide con los filtros.")
        return
    completos = df.apply(checklist_completo, axis=1)
    st.metric("Checklists 100% completos", f"{round(100 * completos.mean())}%")
    fases = pd.DataFrame({
        "Fase": ["Preoperatoria", "Firmas", "Intraoperatoria", "Postoperatoria"],
        "% completo": [
            round(100 * df["preop_completa"].astype(bool).mean()),
            round(100 * df["firmas_preop_completas"].astype(bool).mean()),
            round(100 * df["intraop_completa"].astype(bool).mean()),
            round(100 * df["postop_completa"].astype(bool).mean()),
        ],
    })
    st.bar_chart(fases, x="Fase", y="% completo", width="stretch")
    comp_mes = pd.DataFrame({
        "Mes": [f"{MESES[m]} {y}" for y, m in meta["meses"]],
        "Completos %": [round(100 * completos[pd.to_datetime(df['fecha_cirugia'], errors='coerce').dt.to_period('M') == pd.Period(f'{y}-{m:02d}', freq='M')].mean()) if completos[pd.to_datetime(df['fecha_cirugia'], errors='coerce').dt.to_period('M') == pd.Period(f'{y}-{m:02d}', freq='M')].size else 0 for y, m in meta["meses"]],
    })
    st.subheader("% de checklists completos por mes")
    st.bar_chart(comp_mes, x="Mes", y="Completos %", width="stretch")
    pend = df[~completos]
    st.subheader(f"Cirugías con checklist incompleto ({len(pend)})")
    if pend.empty:
        st.success("Todas las cirugías filtradas tienen el checklist completo.")
    else:
        def _ok(v):
            return str(v).lower() in ("true", "1")
        def _faltan(r):
            return "; ".join(n for n, v in [("Preop", r["preop_completa"]), ("Firmas", r["firmas_preop_completas"]),
                                             ("Intraop", r["intraop_completa"]), ("Postop", r["postop_completa"])] if not _ok(v))
        vista = pend[["id", "fecha_cirugia", "nombre_paciente", "procedimiento", "cirujano"]].copy()
        vista["Faltan"] = pend.apply(_faltan, axis=1).values
        st.dataframe(vista, width="stretch", hide_index=True)


def _panel_historia(data_dir):
    st.caption("Registros de historia clínica (evoluciones y checklists archivados). Solo datos agregados.")
    ini, fin = _rango_fechas("met_rango_hist")
    hist = load_historia(get_paths(data_dir, "assets")["historia_clinica"])
    if hist.empty:
        st.info("Sin registros de historia clínica.")
        return
    fr = pd.to_datetime(hist["fecha_registro"], errors="coerce").dt.normalize()
    h = hist[(fr >= pd.Timestamp(ini)) & (fr <= pd.Timestamp(fin))]
    meses = _meses_rango(ini, fin)[-12:]
    st.caption(f"{len(h)} registros en el rango.")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Registros por mes")
        st.bar_chart(_por_mes(h, "fecha_registro", meses), x="Mes", y="Cantidad", width="stretch")
    with g2:
        st.subheader("Registros por tipo")
        tipos = h["tipo_registro"].astype(str).str.strip().replace("", "Evolución clínica").value_counts()
        st.bar_chart(pd.DataFrame({"Tipo": tipos.index, "Registros": tipos.values}), x="Tipo", y="Registros", width="stretch")
    g3, g4 = st.columns(2)
    with g3:
        st.subheader("Procedimientos con más registros")
        st.bar_chart(_conteo(h["procedimiento"]).rename(columns={"procedimiento": "Procedimiento", "Cantidad": "Registros"}).head(8), x="Procedimiento", y="Registros", width="stretch")
    with g4:
        st.subheader("Pacientes con más registros (conteo)")
        st.bar_chart(_conteo(h["paciente"]).rename(columns={"paciente": "Paciente", "Cantidad": "Registros"}).head(8), x="Paciente", y="Registros", width="stretch")


def _panel_central(data_dir):
    st.caption("Datos de la central de esterilización. Los sets e insumos son estado actual; las cargas respetan el rango de fechas.")
    ini, fin = _rango_fechas("met_rango_central")
    instrumental, cargas, insumos, equipos = _central(data_dir, ini, fin)
    if instrumental.empty and cargas.empty and insumos.empty and equipos.empty:
        st.info("Sin datos de esterilización.")
        return
    meses = _meses_rango(ini, fin)[-12:]
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown("**Sets por estado**")
        if instrumental.empty:
            st.info("Sin sets.")
        else:
            estados = instrumental["estado"].astype(str).str.strip().value_counts()
            st.bar_chart(pd.DataFrame({"Estado": estados.index, "Sets": estados.values}), x="Estado", y="Sets", width="stretch")
    with e2:
        st.markdown("**Cargas por resultado**")
        if cargas.empty:
            st.info("Sin cargas en el rango.")
        else:
            res = cargas["resultado"].value_counts()
            st.bar_chart(pd.DataFrame({"Resultado": res.index, "Cargas": res.values}), x="Resultado", y="Cargas", width="stretch")
    with e3:
        st.markdown("**Cargas por mes**")
        if cargas.empty:
            st.info("Sin cargas en el rango.")
        else:
            st.bar_chart(_por_mes(cargas, "fecha", meses), x="Mes", y="Cantidad", width="stretch")
    if not insumos.empty:
        st.markdown("**Insumos que requieren atención**")
        atencion = insumos[(numeros(insumos["stock"]) <= numeros(insumos["stock_minimo"])) | (fechas_vencidos_insumos(insumos))]
        if atencion.empty:
            st.success("Ningún insumo bajo el mínimo ni vencido.")
        else:
            st.dataframe(atencion[["nombre", "stock", "stock_minimo", "unidad", "lote", "fecha_vencimiento", "proveedor"]], width="stretch", hide_index=True)
    if not equipos.empty:
        st.markdown("**Equipos con mantenimiento próximo**")
        prox_df = equipos[equipos["estado"] != "Fuera de servicio"].copy()
        prox_df["_prox"] = pd.to_datetime(prox_df["proximo_mantenimiento"], errors="coerce")
        prox_df = prox_df[prox_df["_prox"].notna()].sort_values("_prox")
        if prox_df.empty:
            st.info("Sin fechas de mantenimiento.")
        else:
            st.dataframe(prox_df[["nombre", "tipo", "estado", "proximo_mantenimiento", "proveedor_mantenimiento"]], width="stretch", hide_index=True)


def _graficas_y_descarga(data_dir):
    cirugias = load_cirugias(get_paths(data_dir, "assets")["cirugias"])
    if cirugias.empty:
        st.info("Sin cirugías para exportar.")
        return
    df, meta = _filtros_cirugia(cirugias)
    if df.empty:
        st.warning("Ninguna cirugía coincide con los filtros.")
        return
    meses = meta["meses"]
    completos = df.apply(checklist_completo, axis=1)
    fases = pd.DataFrame({
        "Fase": ["Preoperatoria", "Firmas", "Intraoperatoria", "Postoperatoria"],
        "% completo": [round(100 * df["preop_completa"].astype(bool).mean()), round(100 * df["firmas_preop_completas"].astype(bool).mean()),
                       round(100 * df["intraop_completa"].astype(bool).mean()), round(100 * df["postop_completa"].astype(bool).mean())],
    })
    instrumental, cargas, insumos, equipos = _central(data_dir, meta["ini"], meta["fin"])
    graficas = [
        ("Cirugías por mes", _por_mes(df, "fecha_cirugia", meses)),
        ("Procedimientos", _conteo(df["procedimiento"]).rename(columns={"procedimiento": "Procedimiento", "Cantidad": "Cirugías"})),
        ("Instituciones", _conteo(df["institucion"]).rename(columns={"institucion": "Institución", "Cantidad": "Cirugías"})),
        ("Cirujanos", _conteo(df.get("cirujano", pd.Series(dtype=str))).rename(columns={"cirujano": "Cirujano/a", "Cantidad": "Cirugías"})),
        ("Sexo", _conteo(df["sexo"]).rename(columns={"sexo": "Sexo", "Cantidad": "Cirugías"})),
        ("Checklist por fase", fases),
    ]
    if not instrumental.empty:
        estados = instrumental["estado"].astype(str).str.strip().value_counts()
        graficas.append(("Sets por estado", pd.DataFrame({"Estado": estados.index, "Sets": estados.values})))
    if not cargas.empty:
        res = cargas["resultado"].value_counts()
        graficas.append(("Cargas por resultado", pd.DataFrame({"Resultado": res.index, "Cargas": res.values})))
        graficas.append(("Cargas por mes", _por_mes(cargas, "fecha", meses)))
    kp = _kpis_cirugia(df, meta)
    vencidos = int(sets_vencidos(instrumental).sum()) if not instrumental.empty else 0
    sets_vig = int(((instrumental["estado"] == "Esterilizado") & ~sets_vencidos(instrumental)).sum()) if not instrumental.empty else 0
    detalle = df[["id", "fecha_cirugia", "nombre_paciente", "numero_documento", "institucion", "procedimiento", "cirujano", "sexo", "edad",
                  "checklist_iniciado", "preop_completa", "firmas_preop_completas", "intraop_completa", "postop_completa"]].copy()
    detalle["checklist_completo"] = completos.values
    resumen = [("Rango", f"{meta['ini']} a {meta['fin']}"), ("Cirugías en el filtro", len(df)), ("Cirugías este mes", kp["mes"]),
               ("Cirugías este año", kp["anio"]), ("Checklists completos (%)", kp["pct"]), ("Sets estériles vigentes", sets_vig),
               ("Sets vencidos", vencidos)]
    excel = _excel_bytes(resumen, graficas, detalle)
    st.download_button("⬇️ Descargar Excel con métricas y gráficas", data=excel,
                       file_name=f"metricas_{meta['ini']}_{meta['fin']}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    st.caption("El Excel incluye una hoja por gráfica con su gráfico de barras y la hoja 'Cirugías' con el detalle filtrado.")


def _titulo():
    partes = []
    r = st.session_state.get("met_rango")
    if r:
        try:
            ini, fin = r if isinstance(r, tuple) else (r, r)
            partes.append(f"{ini} → {fin}")
        except Exception:
            pass
    for k, lbl in [("met_inst", "Institución"), ("met_proc", "Procedimiento"),
                   ("met_cir", "Cirujano/a"), ("met_sexo", "Sexo")]:
        v = st.session_state.get(k) or []
        if v:
            txt = ", ".join(map(str, v[:3])) + ("…" if len(v) > 3 else "")
            partes.append(f"{lbl}: {txt}")
    e = st.session_state.get("met_estado")
    if e and e != "Todos":
        partes.append(f"Checklist: {e}")
    sel = " · ".join(partes)
    if len(sel) > 140:
        sel = sel[:137] + "…"
    return "📊 Métricas y Gráficas" + (f" — {sel}" if sel else "")


def render_metricas(data_dir: str = "data", sidebar=None):
    st.title(_titulo())
    st.caption("Indicadores agregados del servicio. No muestran datos de pacientes individuales.")
    paneles = {
        "📊 Resumen": _panel_resumen,
        "🏥 Cirugía": _panel_cirugia,
        "✅ Checklist": _panel_checklist,
        "📋 Historia clínica": _panel_historia,
        "🧼 Central de esterilización": _panel_central,
        "📥 Descargas": lambda d: _graficas_y_descarga(d),
    }
    panel = botones_nav(list(paneles), "panel_metricas", contenedor=sidebar or st.sidebar, titulo="Métricas")
    paneles[panel](data_dir)


def fechas_vencidos_insumos(insumos: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(insumos["fecha_vencimiento"], errors="coerce").dt.normalize() < pd.Timestamp(date.today()).normalize()
