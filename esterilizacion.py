import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from ai_assistant import ClinicalAIAssistant


SCHEMAS = {
    "proveedores": ["id", "nombre", "nit", "categoria", "contacto", "telefono", "email", "productos_servicios", "estado"],
    "instrumental": [
        "id", "codigo", "nombre", "tipo", "especialidad", "cantidad_piezas", "metodo_esterilizacion", "tipo_empaque",
        "estado", "ubicacion", "fecha_esterilizacion", "fecha_vencimiento", "carga_id", "proveedor", "observaciones",
    ],
    "cargas": [
        "id", "fecha", "equipo", "metodo", "programa", "temperatura_c", "tiempo_min", "presion_psi", "operador", "sets",
        "contiene_implantes", "bowie_dick", "indicador_quimico", "indicador_biologico", "lote_biologico", "resultado",
        "observaciones",
    ],
    "insumos": ["id", "nombre", "categoria", "unidad", "stock", "stock_minimo", "lote", "fecha_vencimiento", "proveedor", "ubicacion"],
    "movimientos_insumos": ["id", "fecha", "insumo", "tipo", "cantidad", "responsable", "observaciones"],
    "equipos": [
        "id", "nombre", "tipo", "marca", "modelo", "serial", "ubicacion", "estado", "ultimo_mantenimiento",
        "proximo_mantenimiento", "ultima_validacion", "proveedor_mantenimiento",
    ],
    "despachos": ["id", "fecha", "tipo", "set_codigo", "destino", "cirugia_id", "entrega", "recibe", "observaciones"],
}

TIPOS_INSTRUMENTAL = ["Set / bandeja", "Instrumento individual", "Material en consignación", "Dispositivo termosensible", "Textil / ropa quirúrgica"]
ESPECIALIDADES = ["General", "Ortopedia", "Ginecobstetricia", "Urología", "Neurocirugía", "Oftalmología", "Otorrinolaringología", "Cardiovascular", "Plástica", "Laparoscopia", "Otra"]
METODOS = ["Vapor (autoclave)", "Peróxido de hidrógeno (plasma)", "Óxido de etileno", "Formaldehído", "Desinfección de alto nivel"]
VIDA_UTIL_EMPAQUE = {
    "Textil doble": 15,
    "Papel crepado": 30,
    "Polipropileno no tejido (SMS)": 90,
    "Bolsa mixta papel-polímero": 180,
    "Contenedor rígido": 180,
    "Tyvek": 365,
}
ESTADOS_SET = ["Sucio", "En lavado", "Empacado", "En cuarentena", "Esterilizado", "Despachado", "En mantenimiento", "De baja"]
CATEGORIAS_INSUMO = ["Indicador químico", "Indicador biológico", "Test Bowie-Dick", "Empaque", "Cinta / sello", "Detergente / desinfectante", "Lubricante", "Elemento de protección personal", "Otro"]
UNIDADES = ["Unidad", "Caja", "Rollo", "Litro", "Galón", "Paquete"]
TIPOS_EQUIPO = ["Autoclave de vapor", "Esterilizador de peróxido", "Esterilizador de óxido de etileno", "Lavadora termodesinfectora", "Lavadora ultrasónica", "Selladora", "Incubadora de biológicos", "Otro"]
ESTADOS_EQUIPO = ["Operativo", "En mantenimiento", "Fuera de servicio"]
CATEGORIAS_PROVEEDOR = ["Instrumental", "Insumos de esterilización", "Mantenimiento de equipos", "Material en consignación", "Validación / calibración", "Otro"]
RESULTADOS_QUIMICO = ["Viraje correcto", "Viraje incorrecto"]
RESULTADOS_BIOLOGICO = ["Negativo", "Positivo", "Pendiente", "No aplica"]
RESULTADOS_BOWIE = ["No aplica", "Correcto", "Fallido"]
ROL_ADMIN = "Administrador"
DIAS_ALERTA_VENCIMIENTO = 7
DIAS_ALERTA_MANTENIMIENTO = 15


def _dir(data_dir: str) -> str:
    ruta = os.path.join(data_dir, "esterilizacion")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def cargar(data_dir: str, nombre: str) -> pd.DataFrame:
    ruta = os.path.join(_dir(data_dir), f"{nombre}.csv")
    columnas = SCHEMAS[nombre]
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False) if os.path.exists(ruta) else pd.DataFrame(columns=columnas)
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    return df[columnas].copy()


def guardar(data_dir: str, nombre: str, df: pd.DataFrame):
    df.to_csv(os.path.join(_dir(data_dir), f"{nombre}.csv"), index=False)


def agregar(data_dir: str, nombre: str, fila: dict) -> str:
    df = cargar(data_dir, nombre)
    nuevo_id = str(int(pd.to_numeric(df["id"], errors="coerce").fillna(0).max()) + 1) if not df.empty else "1"
    fila = {col: str(fila.get(col, "")) for col in SCHEMAS[nombre]}
    fila["id"] = nuevo_id
    guardar(data_dir, nombre, pd.concat([df, pd.DataFrame([fila])], ignore_index=True))
    return nuevo_id


def fechas(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, errors="coerce").dt.date


def numeros(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce").fillna(0)


def resultado_carga(bowie_dick: str, quimico: str, biologico: str, contiene_implantes: bool) -> str:
    if bowie_dick == "Fallido" or quimico == "Viraje incorrecto" or biologico == "Positivo":
        return "Rechazada"
    if biologico == "Pendiente" or (contiene_implantes and biologico != "Negativo"):
        return "En cuarentena"
    return "Liberada"


def aplicar_resultado_a_sets(data_dir: str, carga: dict):
    instrumental = cargar(data_dir, "instrumental")
    codigos = [c for c in str(carga["sets"]).split(";") if c]
    mask = instrumental["codigo"].isin(codigos)
    if carga["resultado"] == "Liberada":
        fecha_carga = pd.to_datetime(carga["fecha"], errors="coerce")
        fecha_carga = date.today() if pd.isna(fecha_carga) else fecha_carga.date()
        instrumental.loc[mask, "estado"] = "Esterilizado"
        instrumental.loc[mask, "fecha_esterilizacion"] = fecha_carga.isoformat()
        instrumental.loc[mask, "fecha_vencimiento"] = instrumental.loc[mask, "tipo_empaque"].apply(
            lambda e: (fecha_carga + timedelta(days=VIDA_UTIL_EMPAQUE.get(e, 30))).isoformat()
        )
    else:
        instrumental.loc[mask, "estado"] = "En cuarentena" if carga["resultado"] == "En cuarentena" else "Empacado"
        instrumental.loc[mask, ["fecha_esterilizacion", "fecha_vencimiento"]] = ""
    instrumental.loc[mask, "carga_id"] = str(carga["id"])
    guardar(data_dir, "instrumental", instrumental)


def sets_vencidos(instrumental: pd.DataFrame) -> pd.Series:
    return (instrumental["estado"] == "Esterilizado") & (fechas(instrumental["fecha_vencimiento"]) < date.today())


def sets_por_vencer(instrumental: pd.DataFrame) -> pd.Series:
    venc = fechas(instrumental["fecha_vencimiento"])
    return (instrumental["estado"] == "Esterilizado") & (venc >= date.today()) & (venc <= date.today() + timedelta(days=DIAS_ALERTA_VENCIMIENTO))


def nombres_proveedores(data_dir: str) -> list:
    proveedores = cargar(data_dir, "proveedores")
    return [""] + sorted(proveedores.loc[proveedores["estado"] != "Inactivo", "nombre"].tolist())


def tabla(df: pd.DataFrame, columnas: dict):
    vista = df[list(columnas.keys())].rename(columns=columnas)
    st.dataframe(vista, width="stretch", hide_index=True)


def filtrar(df: pd.DataFrame, clave: str, pills=None, selects=(), fecha=None) -> pd.DataFrame:
    total = len(df)
    if total == 0:
        return df
    cols = st.columns([3] + [2] * (len(selects) + (1 if fecha else 0)))
    texto = cols[0].text_input("🔎 Buscar", key=f"filtro_texto_{clave}", placeholder="Escriba cualquier dato: código, nombre, lote…")
    resultado = df
    for i, (col, titulo) in enumerate(selects):
        elegidos = cols[i + 1].multiselect(titulo, sorted(v for v in df[col].unique() if v), key=f"filtro_{col}_{clave}", placeholder="Todos")
        if elegidos:
            resultado = resultado[resultado[col].isin(elegidos)]
    if fecha:
        rango = cols[-1].date_input("Rango de fechas", value=(), key=f"filtro_fecha_{clave}")
        if len(rango) == 2:
            dias = fechas(resultado[fecha])
            resultado = resultado[(dias >= rango[0]) & (dias <= rango[1])]
    if pills:
        col, titulo, orden = pills
        conteo = df[col].value_counts()
        valores = [v for v in orden if v in conteo.index] + [v for v in conteo.index if v not in orden]
        elegidos = st.pills(titulo, valores, selection_mode="multi", format_func=lambda v: f"{v} ({conteo[v]})", key=f"filtro_pills_{clave}")
        if elegidos:
            resultado = resultado[resultado[col].isin(elegidos)]
    if texto.strip():
        patron = texto.strip().lower()
        resultado = resultado[resultado.apply(lambda c: c.astype(str).str.lower().str.contains(patron, regex=False)).any(axis=1)]
    st.caption(f"Mostrando {len(resultado)} de {total} registros." + ("" if len(resultado) == total else " Quite los filtros para ver todos."))
    return resultado


REFERENCIAS = {
    "proveedores": [("instrumental", "proveedor"), ("insumos", "proveedor"), ("equipos", "proveedor_mantenimiento")],
    "equipos": [("cargas", "equipo")],
    "insumos": [("movimientos_insumos", "insumo")],
}


def renombrar_referencias(data_dir: str, nombre: str, anterior: str, nuevo: str):
    for tabla_ref, col in REFERENCIAS.get(nombre, []):
        df = cargar(data_dir, tabla_ref)
        if (df[col] == anterior).any():
            df.loc[df[col] == anterior, col] = nuevo
            guardar(data_dir, tabla_ref, df)


def devolver_sets_de_cargas_eliminadas(data_dir: str, eliminadas: pd.DataFrame):
    instrumental = cargar(data_dir, "instrumental")
    mask = instrumental["carga_id"].isin(eliminadas["id"]) & instrumental["estado"].isin(["Esterilizado", "En cuarentena"])
    instrumental.loc[mask, "estado"] = "Empacado"
    instrumental.loc[mask, ["fecha_esterilizacion", "fecha_vencimiento", "carga_id"]] = ""
    guardar(data_dir, "instrumental", instrumental)


def editor(data_dir: str, nombre: str, columnas: dict, bloqueadas=(), opciones=None, clave=None, al_eliminar=None, nota=""):
    df = cargar(data_dir, nombre)
    if df.empty:
        return
    opciones = opciones or {}
    with st.expander("✏️ Editar o eliminar registros"):
        st.caption(("Edite las celdas o marque Eliminar y pulse Guardar cambios. La eliminación no se puede deshacer. " + nota).strip())
        vista = df[["id"] + list(columnas)].copy()
        vista.insert(0, "eliminar", False)
        config = {"eliminar": st.column_config.CheckboxColumn("Eliminar"), "id": st.column_config.TextColumn("ID")}
        for col, titulo in columnas.items():
            if col in opciones:
                valores = list(dict.fromkeys(list(opciones[col]) + df[col].tolist()))
                config[col] = st.column_config.SelectboxColumn(titulo, options=valores)
            else:
                config[col] = st.column_config.TextColumn(titulo)
        editado = st.data_editor(vista, column_config=config, disabled=["id", *bloqueadas], hide_index=True, width="stretch", key=f"editor_{nombre}")
        if st.button("Guardar cambios", key=f"guardar_editor_{nombre}", type="primary"):
            editado = editado.fillna("")
            ids_eliminar = editado.loc[editado["eliminar"] == True, "id"].tolist()
            cambios = editado[~editado["id"].isin(ids_eliminar)]
            claves = cambios[clave].astype(str).str.strip().str.lower() if clave else pd.Series(dtype=str)
            if clave and (claves == "").any():
                st.error(f"El campo {columnas[clave]} no puede quedar vacío.")
            elif clave and claves.duplicated().any():
                st.error(f"Hay valores repetidos en {columnas[clave]}.")
            else:
                for _, fila in cambios.iterrows():
                    idx = df.index[df["id"] == fila["id"]][0]
                    for col in columnas:
                        if col in bloqueadas:
                            continue
                        valor = str(fila[col]).strip()
                        if col == clave and valor != df.at[idx, col]:
                            renombrar_referencias(data_dir, nombre, df.at[idx, col], valor)
                        df.at[idx, col] = valor
                eliminados = df[df["id"].isin(ids_eliminar)]
                guardar(data_dir, nombre, df[~df["id"].isin(ids_eliminar)])
                if al_eliminar and not eliminados.empty:
                    al_eliminar(data_dir, eliminados)
                st.success(f"Cambios guardados. Registros eliminados: {len(eliminados)}.")
                st.rerun()


def render_panel(data_dir: str):
    instrumental = cargar(data_dir, "instrumental")
    cargas = cargar(data_dir, "cargas")
    insumos = cargar(data_dir, "insumos")
    equipos = cargar(data_dir, "equipos")

    vencidos = instrumental[sets_vencidos(instrumental)]
    por_vencer = instrumental[sets_por_vencer(instrumental)]
    disponibles = instrumental[(instrumental["estado"] == "Esterilizado") & ~sets_vencidos(instrumental)]
    en_proceso = instrumental[instrumental["estado"].isin(["Sucio", "En lavado", "Empacado", "En cuarentena"])]
    cuarentena = cargas[cargas["resultado"] == "En cuarentena"]
    bajo_stock = insumos[numeros(insumos["stock"]) <= numeros(insumos["stock_minimo"])]
    insumos_vencidos = insumos[fechas(insumos["fecha_vencimiento"]) < date.today()]
    limite_mtto = date.today() + timedelta(days=DIAS_ALERTA_MANTENIMIENTO)
    mtto = equipos[(fechas(equipos["proximo_mantenimiento"]) <= limite_mtto) & (equipos["estado"] != "Fuera de servicio")]
    hoy = cargas[fechas(cargas["fecha"]) == date.today()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sets estériles disponibles", len(disponibles))
    c2.metric("Sets en proceso", len(en_proceso))
    c3.metric("Sets despachados", int((instrumental["estado"] == "Despachado").sum()))
    c4.metric("Cargas de hoy", len(hoy))
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Sets vencidos", len(vencidos))
    c6.metric(f"Vencen en {DIAS_ALERTA_VENCIMIENTO} días", len(por_vencer))
    c7.metric("Insumos bajo mínimo", len(bajo_stock))
    c8.metric("Cargas en cuarentena", len(cuarentena))

    st.divider()
    st.subheader("🚨 Alertas")
    sin_alertas = True
    if not vencidos.empty:
        sin_alertas = False
        st.error(f"{len(vencidos)} set(s) con esterilidad vencida: no despachar, deben reprocesarse.")
        tabla(vencidos, {"codigo": "Código", "nombre": "Nombre", "ubicacion": "Ubicación", "fecha_vencimiento": "Venció"})
    if not cuarentena.empty:
        sin_alertas = False
        st.warning(f"{len(cuarentena)} carga(s) en cuarentena esperando resultado del indicador biológico.")
        tabla(cuarentena, {"id": "Carga", "fecha": "Fecha", "equipo": "Equipo", "sets": "Sets", "lote_biologico": "Lote biológico"})
    if not por_vencer.empty:
        sin_alertas = False
        st.warning(f"{len(por_vencer)} set(s) vencen en los próximos {DIAS_ALERTA_VENCIMIENTO} días.")
        tabla(por_vencer, {"codigo": "Código", "nombre": "Nombre", "ubicacion": "Ubicación", "fecha_vencimiento": "Vence"})
    if not bajo_stock.empty:
        sin_alertas = False
        st.warning(f"{len(bajo_stock)} insumo(s) en o por debajo del stock mínimo.")
        tabla(bajo_stock, {"nombre": "Insumo", "stock": "Stock", "stock_minimo": "Mínimo", "unidad": "Unidad", "proveedor": "Proveedor"})
    if not insumos_vencidos.empty:
        sin_alertas = False
        st.error(f"{len(insumos_vencidos)} insumo(s) con fecha de vencimiento cumplida.")
        tabla(insumos_vencidos, {"nombre": "Insumo", "lote": "Lote", "fecha_vencimiento": "Venció"})
    if not mtto.empty:
        sin_alertas = False
        st.warning(f"{len(mtto)} equipo(s) con mantenimiento vencido o dentro de {DIAS_ALERTA_MANTENIMIENTO} días.")
        tabla(mtto, {"nombre": "Equipo", "serial": "Serial", "proximo_mantenimiento": "Próximo mantenimiento", "proveedor_mantenimiento": "Proveedor"})
    if sin_alertas:
        st.success("Sin alertas activas.")


def render_inventario(data_dir: str):
    instrumental = cargar(data_dir, "instrumental")

    st.subheader("📦 Inventario de instrumental y sets")
    vista = instrumental.copy()
    vista.loc[sets_vencidos(vista), "estado"] = "Vencido"
    vista = filtrar(
        vista, "instrumental", pills=("estado", "Estado", ESTADOS_SET + ["Vencido"]),
        selects=[("especialidad", "Especialidad"), ("tipo", "Tipo"), ("proveedor", "Proveedor")],
    )

    if vista.empty:
        st.info("No hay instrumental registrado con ese criterio.")
    else:
        tabla(vista, {
            "codigo": "Código", "nombre": "Nombre", "tipo": "Tipo", "especialidad": "Especialidad", "cantidad_piezas": "Piezas",
            "metodo_esterilizacion": "Método", "tipo_empaque": "Empaque", "estado": "Estado", "ubicacion": "Ubicación",
            "fecha_esterilizacion": "Esterilizado", "fecha_vencimiento": "Vence", "carga_id": "Carga", "proveedor": "Proveedor",
        })

    with st.expander("➕ Registrar set o instrumento"):
        with st.form("form_instrumental", clear_on_submit=True):
            a1, a2, a3 = st.columns(3)
            codigo = a1.text_input("Código *")
            nombre = a2.text_input("Nombre *")
            tipo = a3.selectbox("Tipo", TIPOS_INSTRUMENTAL)
            b1, b2, b3 = st.columns(3)
            especialidad = b1.selectbox("Especialidad", ESPECIALIDADES)
            piezas = b2.number_input("Cantidad de piezas", min_value=1, value=1, step=1)
            metodo = b3.selectbox("Método de esterilización", METODOS)
            c1, c2, c3 = st.columns(3)
            empaque = c1.selectbox("Tipo de empaque", list(VIDA_UTIL_EMPAQUE.keys()), format_func=lambda e: f"{e} ({VIDA_UTIL_EMPAQUE[e]} días)")
            estado = c2.selectbox("Estado inicial", ESTADOS_SET, index=ESTADOS_SET.index("Sucio"))
            ubicacion = c3.text_input("Ubicación")
            proveedor = st.selectbox("Proveedor", nombres_proveedores(data_dir))
            observaciones = st.text_area("Observaciones")
            if st.form_submit_button("Guardar"):
                codigo = codigo.strip().upper()
                if not codigo or not nombre.strip():
                    st.error("El código y el nombre son obligatorios.")
                elif codigo in instrumental["codigo"].values:
                    st.error(f"Ya existe un set con el código {codigo}.")
                elif estado in ["Esterilizado", "En cuarentena", "Despachado"]:
                    st.error("Un set solo queda estéril al liberar una carga. Regístrelo como Sucio, En lavado o Empacado.")
                else:
                    agregar(data_dir, "instrumental", {
                        "codigo": codigo, "nombre": nombre.strip(), "tipo": tipo, "especialidad": especialidad,
                        "cantidad_piezas": int(piezas), "metodo_esterilizacion": metodo, "tipo_empaque": empaque,
                        "estado": estado, "ubicacion": ubicacion.strip(), "proveedor": proveedor, "observaciones": observaciones.strip(),
                    })
                    st.success(f"Set {codigo} registrado.")
                    st.rerun()

    if not instrumental.empty:
        with st.expander("🔄 Cambiar estado de un set"):
            st.caption("Flujo: Sucio → En lavado → Empacado → (carga de esterilización) → Esterilizado → Despachado → Sucio.")
            with st.form("form_estado_set"):
                e1, e2 = st.columns(2)
                codigo_sel = e1.selectbox(
                    "Set", instrumental["codigo"].tolist(),
                    format_func=lambda c: f"{c} | {instrumental.loc[instrumental['codigo'] == c, 'nombre'].iloc[0]} | {instrumental.loc[instrumental['codigo'] == c, 'estado'].iloc[0]}",
                )
                nuevo_estado = e2.selectbox("Nuevo estado", ["Sucio", "En lavado", "Empacado", "En mantenimiento", "De baja"])
                if st.form_submit_button("Actualizar estado"):
                    mask = instrumental["codigo"] == codigo_sel
                    instrumental.loc[mask, "estado"] = nuevo_estado
                    instrumental.loc[mask, ["fecha_esterilizacion", "fecha_vencimiento"]] = ""
                    guardar(data_dir, "instrumental", instrumental)
                    st.success(f"Set {codigo_sel} actualizado a {nuevo_estado}.")
                    st.rerun()
    editor(
        data_dir, "instrumental",
        {
            "codigo": "Código", "nombre": "Nombre", "tipo": "Tipo", "especialidad": "Especialidad", "cantidad_piezas": "Piezas",
            "metodo_esterilizacion": "Método", "tipo_empaque": "Empaque", "estado": "Estado", "ubicacion": "Ubicación",
            "proveedor": "Proveedor", "observaciones": "Observaciones",
        },
        bloqueadas=["codigo", "estado"],
        opciones={
            "tipo": TIPOS_INSTRUMENTAL, "especialidad": ESPECIALIDADES, "metodo_esterilizacion": METODOS,
            "tipo_empaque": list(VIDA_UTIL_EMPAQUE.keys()), "proveedor": nombres_proveedores(data_dir),
        },
        nota="El código no se edita y el estado se cambia con el formulario de arriba.",
    )


def render_cargas(data_dir: str):
    instrumental = cargar(data_dir, "instrumental")
    cargas = cargar(data_dir, "cargas")
    equipos = cargar(data_dir, "equipos")

    st.subheader("♨️ Cargas de esterilización")
    st.caption(
        "Una carga se libera solo con indicador químico correcto y biológico negativo o no aplicable. "
        "Con biológico pendiente, o con implantes sin biológico negativo, queda en cuarentena. "
        "Bowie-Dick fallido, viraje incorrecto o biológico positivo la rechazan y los sets vuelven a Empacado."
    )

    empacados = instrumental[instrumental["estado"] == "Empacado"]
    esterilizadores = equipos[(equipos["estado"] == "Operativo") & equipos["tipo"].str.contains("Autoclave|Esterilizador")]

    with st.expander("➕ Registrar carga", expanded=cargas.empty):
        if empacados.empty:
            st.info("No hay sets en estado Empacado. Pase los sets a Empacado en la pestaña Inventario.")
        elif esterilizadores.empty:
            st.info("No hay esterilizadores operativos. Registre uno en la pestaña Equipos.")
        else:
            with st.form("form_carga", clear_on_submit=True):
                a1, a2, a3 = st.columns(3)
                fecha = a1.date_input("Fecha", value=date.today(), max_value=date.today())
                equipo = a2.selectbox("Equipo", esterilizadores["nombre"].tolist())
                metodo = a3.selectbox("Método", METODOS[:4])
                b1, b2, b3, b4 = st.columns(4)
                programa = b1.text_input("Programa / ciclo", placeholder="Ej: Instrumental 134 °C")
                temperatura = b2.number_input("Temperatura (°C)", min_value=0.0, value=134.0, step=1.0)
                tiempo = b3.number_input("Tiempo de exposición (min)", min_value=0, value=4, step=1)
                presion = b4.number_input("Presión (psi)", min_value=0.0, value=30.0, step=1.0)
                sets = st.multiselect(
                    "Sets incluidos *", empacados["codigo"].tolist(),
                    format_func=lambda c: f"{c} | {empacados.loc[empacados['codigo'] == c, 'nombre'].iloc[0]}",
                )
                implantes = st.checkbox("La carga contiene implantes")
                c1, c2, c3, c4 = st.columns(4)
                bowie = c1.selectbox("Test Bowie-Dick", RESULTADOS_BOWIE)
                quimico = c2.selectbox("Indicador químico", RESULTADOS_QUIMICO)
                biologico = c3.selectbox("Indicador biológico", RESULTADOS_BIOLOGICO, index=RESULTADOS_BIOLOGICO.index("Pendiente"))
                lote_bio = c4.text_input("Lote del biológico")
                operador = st.text_input("Operador *", value=str(st.session_state.get("usuario", "")))
                observaciones = st.text_area("Observaciones")
                if st.form_submit_button("Registrar carga"):
                    if not sets or not operador.strip():
                        st.error("Debe incluir al menos un set e indicar el operador.")
                    else:
                        carga = {
                            "fecha": fecha.isoformat(), "equipo": equipo, "metodo": metodo, "programa": programa.strip(),
                            "temperatura_c": temperatura, "tiempo_min": int(tiempo), "presion_psi": presion,
                            "operador": operador.strip(), "sets": ";".join(sets), "contiene_implantes": "Sí" if implantes else "No",
                            "bowie_dick": bowie, "indicador_quimico": quimico, "indicador_biologico": biologico,
                            "lote_biologico": lote_bio.strip(), "resultado": resultado_carga(bowie, quimico, biologico, implantes),
                            "observaciones": observaciones.strip(),
                        }
                        carga["id"] = agregar(data_dir, "cargas", carga)
                        aplicar_resultado_a_sets(data_dir, carga)
                        st.success(f"Carga #{carga['id']} registrada: {carga['resultado']}.")
                        st.rerun()

    cuarentena = cargas[cargas["resultado"] == "En cuarentena"]
    if not cuarentena.empty:
        with st.expander("🧪 Registrar resultado de biológico pendiente", expanded=True):
            with st.form("form_biologico"):
                d1, d2 = st.columns(2)
                carga_id = d1.selectbox(
                    "Carga en cuarentena", cuarentena["id"].tolist(),
                    format_func=lambda i: f"Carga #{i} | {cuarentena.loc[cuarentena['id'] == i, 'fecha'].iloc[0]} | {cuarentena.loc[cuarentena['id'] == i, 'sets'].iloc[0]}",
                )
                lectura = d2.selectbox("Resultado del indicador biológico", ["Negativo", "Positivo"])
                if st.form_submit_button("Guardar resultado"):
                    idx = cargas.index[cargas["id"] == carga_id][0]
                    cargas.at[idx, "indicador_biologico"] = lectura
                    cargas.at[idx, "resultado"] = resultado_carga(
                        cargas.at[idx, "bowie_dick"], cargas.at[idx, "indicador_quimico"], lectura, cargas.at[idx, "contiene_implantes"] == "Sí"
                    )
                    guardar(data_dir, "cargas", cargas)
                    aplicar_resultado_a_sets(data_dir, cargas.loc[idx].to_dict())
                    st.success(f"Carga #{carga_id}: {cargas.at[idx, 'resultado']}.")
                    st.rerun()

    if cargas.empty:
        st.info("Todavía no hay cargas registradas.")
    else:
        vista = filtrar(
            cargas.iloc[::-1], "cargas", pills=("resultado", "Resultado", ["Liberada", "En cuarentena", "Rechazada"]),
            selects=[("equipo", "Equipo"), ("operador", "Operador")], fecha="fecha",
        )
        tabla(vista, {
            "id": "Carga", "fecha": "Fecha", "equipo": "Equipo", "metodo": "Método", "programa": "Programa",
            "temperatura_c": "°C", "tiempo_min": "Min", "presion_psi": "psi", "sets": "Sets", "contiene_implantes": "Implantes",
            "bowie_dick": "Bowie-Dick", "indicador_quimico": "Químico", "indicador_biologico": "Biológico",
            "resultado": "Resultado", "operador": "Operador", "observaciones": "Observaciones",
        })
    editor(
        data_dir, "cargas",
        {
            "fecha": "Fecha", "equipo": "Equipo", "sets": "Sets", "resultado": "Resultado", "programa": "Programa",
            "temperatura_c": "°C", "tiempo_min": "Min", "presion_psi": "psi", "operador": "Operador",
            "lote_biologico": "Lote biológico", "observaciones": "Observaciones",
        },
        bloqueadas=["fecha", "equipo", "sets", "resultado"],
        al_eliminar=devolver_sets_de_cargas_eliminadas,
        nota="Al eliminar una carga, los sets que seguían estériles o en cuarentena por ella vuelven a Empacado.",
    )


def render_despachos(data_dir: str):
    instrumental = cargar(data_dir, "instrumental")
    despachos = cargar(data_dir, "despachos")

    st.subheader("🚚 Despacho y recepción")
    disponibles = instrumental[(instrumental["estado"] == "Esterilizado") & ~sets_vencidos(instrumental)]
    despachados = instrumental[instrumental["estado"] == "Despachado"]
    usuario = str(st.session_state.get("usuario", ""))

    col_d, col_r = st.columns(2)
    with col_d:
        st.markdown("**Despacho de material estéril**")
        if disponibles.empty:
            st.info("No hay sets estériles vigentes para despachar.")
        else:
            with st.form("form_despacho", clear_on_submit=True):
                set_codigo = st.selectbox(
                    "Set estéril", disponibles["codigo"].tolist(),
                    format_func=lambda c: f"{c} | {disponibles.loc[disponibles['codigo'] == c, 'nombre'].iloc[0]} | vence {disponibles.loc[disponibles['codigo'] == c, 'fecha_vencimiento'].iloc[0]}",
                )
                destino = st.text_input("Destino *", placeholder="Ej: Quirófano 2")
                cirugia_id = st.text_input("ID de cirugía (opcional)")
                recibe = st.text_input("Recibe *")
                obs = st.text_input("Observaciones", key="obs_despacho")
                if st.form_submit_button("Despachar"):
                    if not destino.strip() or not recibe.strip():
                        st.error("El destino y quien recibe son obligatorios.")
                    else:
                        agregar(data_dir, "despachos", {
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "tipo": "Despacho", "set_codigo": set_codigo,
                            "destino": destino.strip(), "cirugia_id": cirugia_id.strip(), "entrega": usuario,
                            "recibe": recibe.strip(), "observaciones": obs.strip(),
                        })
                        instrumental.loc[instrumental["codigo"] == set_codigo, "estado"] = "Despachado"
                        guardar(data_dir, "instrumental", instrumental)
                        st.success(f"Set {set_codigo} despachado a {destino.strip()}.")
                        st.rerun()
    with col_r:
        st.markdown("**Recepción de material usado**")
        if despachados.empty:
            st.info("No hay sets despachados pendientes de devolución.")
        else:
            with st.form("form_recepcion", clear_on_submit=True):
                set_codigo = st.selectbox(
                    "Set devuelto", despachados["codigo"].tolist(),
                    format_func=lambda c: f"{c} | {despachados.loc[despachados['codigo'] == c, 'nombre'].iloc[0]}",
                )
                piezas_ok = st.checkbox("Conteo de piezas completo", value=True)
                entrega = st.text_input("Entrega *")
                obs = st.text_input("Observaciones (faltantes, daños)", key="obs_recepcion")
                if st.form_submit_button("Recibir"):
                    if not entrega.strip():
                        st.error("Indique quién entrega el material.")
                    elif not piezas_ok and not obs.strip():
                        st.error("Si el conteo no está completo, describa el faltante o daño en observaciones.")
                    else:
                        agregar(data_dir, "despachos", {
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "tipo": "Recepción", "set_codigo": set_codigo,
                            "destino": "Central de esterilización", "entrega": entrega.strip(), "recibe": usuario,
                            "observaciones": ("" if piezas_ok else "CONTEO INCOMPLETO. ") + obs.strip(),
                        })
                        mask = instrumental["codigo"] == set_codigo
                        instrumental.loc[mask, "estado"] = "Sucio"
                        instrumental.loc[mask, ["fecha_esterilizacion", "fecha_vencimiento"]] = ""
                        guardar(data_dir, "instrumental", instrumental)
                        st.success(f"Set {set_codigo} recibido y marcado como Sucio.")
                        st.rerun()

    st.divider()
    if despachos.empty:
        st.info("Todavía no hay movimientos de despacho o recepción.")
    else:
        vista = filtrar(
            despachos.iloc[::-1], "despachos", pills=("tipo", "Tipo", ["Despacho", "Recepción"]),
            selects=[("set_codigo", "Set"), ("destino", "Destino")], fecha="fecha",
        )
        tabla(vista, {
            "fecha": "Fecha", "tipo": "Tipo", "set_codigo": "Set", "destino": "Destino", "cirugia_id": "Cirugía",
            "entrega": "Entrega", "recibe": "Recibe", "observaciones": "Observaciones",
        })
    editor(
        data_dir, "despachos",
        {
            "fecha": "Fecha", "tipo": "Tipo", "set_codigo": "Set", "destino": "Destino", "cirugia_id": "Cirugía",
            "entrega": "Entrega", "recibe": "Recibe", "observaciones": "Observaciones",
        },
        bloqueadas=["fecha", "tipo", "set_codigo"],
        nota="Eliminar un movimiento solo lo quita del registro; no cambia el estado del set.",
    )


def render_insumos(data_dir: str):
    insumos = cargar(data_dir, "insumos")
    movimientos = cargar(data_dir, "movimientos_insumos")

    st.subheader("🧴 Insumos y consumibles")
    if insumos.empty:
        st.info("Todavía no hay insumos registrados.")
    else:
        vista = insumos.copy()
        vista["alerta"] = "Al día"
        vista.loc[numeros(vista["stock"]) <= numeros(vista["stock_minimo"]), "alerta"] = "Bajo mínimo"
        vista.loc[fechas(vista["fecha_vencimiento"]) < date.today(), "alerta"] = "Vencido"
        vista = filtrar(
            vista, "insumos", pills=("alerta", "Alerta", ["Vencido", "Bajo mínimo", "Al día"]),
            selects=[("categoria", "Categoría"), ("proveedor", "Proveedor")],
        )
        tabla(vista, {
            "nombre": "Insumo", "categoria": "Categoría", "stock": "Stock", "stock_minimo": "Mínimo", "unidad": "Unidad",
            "lote": "Lote", "fecha_vencimiento": "Vence", "proveedor": "Proveedor", "ubicacion": "Ubicación", "alerta": "Alerta",
        })

    with st.expander("➕ Registrar insumo"):
        with st.form("form_insumo", clear_on_submit=True):
            a1, a2, a3 = st.columns(3)
            nombre = a1.text_input("Nombre *")
            categoria = a2.selectbox("Categoría", CATEGORIAS_INSUMO)
            unidad = a3.selectbox("Unidad", UNIDADES)
            b1, b2, b3 = st.columns(3)
            stock = b1.number_input("Stock inicial", min_value=0.0, value=0.0, step=1.0)
            minimo = b2.number_input("Stock mínimo", min_value=0.0, value=0.0, step=1.0)
            lote = b3.text_input("Lote")
            c1, c2, c3 = st.columns(3)
            vence = c1.date_input("Fecha de vencimiento", value=None)
            proveedor = c2.selectbox("Proveedor", nombres_proveedores(data_dir))
            ubicacion = c3.text_input("Ubicación")
            if st.form_submit_button("Guardar"):
                if not nombre.strip():
                    st.error("El nombre es obligatorio.")
                elif nombre.strip().lower() in insumos["nombre"].str.lower().values:
                    st.error("Ya existe un insumo con ese nombre. Use un movimiento de entrada para sumar stock.")
                else:
                    agregar(data_dir, "insumos", {
                        "nombre": nombre.strip(), "categoria": categoria, "unidad": unidad, "stock": stock, "stock_minimo": minimo,
                        "lote": lote.strip(), "fecha_vencimiento": vence.isoformat() if vence else "", "proveedor": proveedor,
                        "ubicacion": ubicacion.strip(),
                    })
                    st.success("Insumo registrado.")
                    st.rerun()

    if not insumos.empty:
        with st.expander("↕️ Registrar entrada o salida"):
            with st.form("form_movimiento", clear_on_submit=True):
                m1, m2, m3 = st.columns(3)
                insumo = m1.selectbox("Insumo", insumos["nombre"].tolist())
                tipo = m2.selectbox("Tipo", ["Entrada", "Salida"])
                cantidad = m3.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0)
                obs = st.text_input("Observaciones")
                if st.form_submit_button("Registrar movimiento"):
                    idx = insumos.index[insumos["nombre"] == insumo][0]
                    actual = float(numeros(insumos.loc[[idx], "stock"]).iloc[0])
                    if cantidad <= 0:
                        st.error("La cantidad debe ser mayor que cero.")
                    elif tipo == "Salida" and cantidad > actual:
                        st.error(f"Stock insuficiente: hay {actual:g} y se intenta sacar {cantidad:g}.")
                    else:
                        insumos.at[idx, "stock"] = f"{actual + cantidad if tipo == 'Entrada' else actual - cantidad:g}"
                        guardar(data_dir, "insumos", insumos)
                        agregar(data_dir, "movimientos_insumos", {
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "insumo": insumo, "tipo": tipo,
                            "cantidad": f"{cantidad:g}", "responsable": str(st.session_state.get("usuario", "")), "observaciones": obs.strip(),
                        })
                        st.success("Movimiento registrado.")
                        st.rerun()

    if not movimientos.empty:
        st.markdown("**Últimos movimientos**")
        tabla(movimientos.iloc[::-1].head(50), {
            "fecha": "Fecha", "insumo": "Insumo", "tipo": "Tipo", "cantidad": "Cantidad", "responsable": "Responsable", "observaciones": "Observaciones",
        })
    editor(
        data_dir, "insumos",
        {
            "nombre": "Insumo", "categoria": "Categoría", "unidad": "Unidad", "stock": "Stock", "stock_minimo": "Mínimo",
            "lote": "Lote", "fecha_vencimiento": "Vence (AAAA-MM-DD)", "proveedor": "Proveedor", "ubicacion": "Ubicación",
        },
        opciones={"categoria": CATEGORIAS_INSUMO, "unidad": UNIDADES, "proveedor": nombres_proveedores(data_dir)},
        clave="nombre",
    )


def render_equipos(data_dir: str):
    equipos = cargar(data_dir, "equipos")

    st.subheader("⚙️ Equipos")
    if equipos.empty:
        st.info("Todavía no hay equipos registrados.")
    else:
        vista = filtrar(equipos, "equipos", pills=("estado", "Estado", ESTADOS_EQUIPO), selects=[("tipo", "Tipo"), ("ubicacion", "Ubicación")])
        tabla(vista, {
            "nombre": "Equipo", "tipo": "Tipo", "marca": "Marca", "modelo": "Modelo", "serial": "Serial", "ubicacion": "Ubicación",
            "estado": "Estado", "ultimo_mantenimiento": "Último mantenimiento", "proximo_mantenimiento": "Próximo mantenimiento",
            "ultima_validacion": "Última validación", "proveedor_mantenimiento": "Proveedor de mantenimiento",
        })

    with st.expander("➕ Registrar equipo", expanded=equipos.empty):
        with st.form("form_equipo", clear_on_submit=True):
            a1, a2, a3 = st.columns(3)
            nombre = a1.text_input("Nombre *", placeholder="Ej: Autoclave 1")
            tipo = a2.selectbox("Tipo", TIPOS_EQUIPO)
            estado = a3.selectbox("Estado", ESTADOS_EQUIPO)
            b1, b2, b3, b4 = st.columns(4)
            marca = b1.text_input("Marca")
            modelo = b2.text_input("Modelo")
            serial = b3.text_input("Serial")
            ubicacion = b4.text_input("Ubicación")
            c1, c2, c3 = st.columns(3)
            ultimo = c1.date_input("Último mantenimiento", value=None)
            proximo = c2.date_input("Próximo mantenimiento", value=None)
            validacion = c3.date_input("Última validación / calibración", value=None)
            proveedor = st.selectbox("Proveedor de mantenimiento", nombres_proveedores(data_dir))
            if st.form_submit_button("Guardar"):
                if not nombre.strip():
                    st.error("El nombre es obligatorio.")
                elif nombre.strip().lower() in equipos["nombre"].str.lower().values:
                    st.error("Ya existe un equipo con ese nombre.")
                else:
                    agregar(data_dir, "equipos", {
                        "nombre": nombre.strip(), "tipo": tipo, "marca": marca.strip(), "modelo": modelo.strip(), "serial": serial.strip(),
                        "ubicacion": ubicacion.strip(), "estado": estado, "ultimo_mantenimiento": ultimo.isoformat() if ultimo else "",
                        "proximo_mantenimiento": proximo.isoformat() if proximo else "",
                        "ultima_validacion": validacion.isoformat() if validacion else "", "proveedor_mantenimiento": proveedor,
                    })
                    st.success("Equipo registrado.")
                    st.rerun()

    if not equipos.empty:
        with st.expander("🛠️ Registrar mantenimiento o cambio de estado"):
            with st.form("form_mantenimiento"):
                d1, d2 = st.columns(2)
                equipo = d1.selectbox("Equipo", equipos["nombre"].tolist())
                estado = d2.selectbox("Estado", ESTADOS_EQUIPO)
                e1, e2 = st.columns(2)
                realizado = e1.date_input("Mantenimiento realizado el", value=None, max_value=date.today())
                proximo = e2.date_input("Próximo mantenimiento", value=None)
                if st.form_submit_button("Actualizar equipo"):
                    idx = equipos.index[equipos["nombre"] == equipo][0]
                    equipos.at[idx, "estado"] = estado
                    if realizado:
                        equipos.at[idx, "ultimo_mantenimiento"] = realizado.isoformat()
                    if proximo:
                        equipos.at[idx, "proximo_mantenimiento"] = proximo.isoformat()
                    guardar(data_dir, "equipos", equipos)
                    st.success(f"{equipo} actualizado.")
                    st.rerun()
    editor(
        data_dir, "equipos",
        {
            "nombre": "Equipo", "tipo": "Tipo", "marca": "Marca", "modelo": "Modelo", "serial": "Serial", "ubicacion": "Ubicación",
            "estado": "Estado", "ultimo_mantenimiento": "Último mantenimiento (AAAA-MM-DD)",
            "proximo_mantenimiento": "Próximo mantenimiento (AAAA-MM-DD)", "ultima_validacion": "Última validación (AAAA-MM-DD)",
            "proveedor_mantenimiento": "Proveedor de mantenimiento",
        },
        opciones={"tipo": TIPOS_EQUIPO, "estado": ESTADOS_EQUIPO, "proveedor_mantenimiento": nombres_proveedores(data_dir)},
        clave="nombre",
    )


def render_proveedores(data_dir: str):
    proveedores = cargar(data_dir, "proveedores")

    st.subheader("🏢 Proveedores")
    if proveedores.empty:
        st.info("Todavía no hay proveedores registrados.")
    else:
        vista = filtrar(proveedores, "proveedores", pills=("categoria", "Categoría", CATEGORIAS_PROVEEDOR), selects=[("estado", "Estado")])
        tabla(vista, {
            "nombre": "Proveedor", "nit": "NIT", "categoria": "Categoría", "contacto": "Contacto", "telefono": "Teléfono",
            "email": "Correo", "productos_servicios": "Productos / servicios", "estado": "Estado",
        })

    with st.expander("➕ Registrar proveedor", expanded=proveedores.empty):
        with st.form("form_proveedor", clear_on_submit=True):
            a1, a2, a3 = st.columns(3)
            nombre = a1.text_input("Razón social *")
            nit = a2.text_input("NIT *")
            categoria = a3.selectbox("Categoría", CATEGORIAS_PROVEEDOR)
            b1, b2, b3 = st.columns(3)
            contacto = b1.text_input("Persona de contacto")
            telefono = b2.text_input("Teléfono")
            email = b3.text_input("Correo")
            productos = st.text_area("Productos o servicios que suministra")
            if st.form_submit_button("Guardar"):
                if not nombre.strip() or not nit.strip():
                    st.error("La razón social y el NIT son obligatorios.")
                elif nit.strip() in proveedores["nit"].values:
                    st.error("Ya existe un proveedor con ese NIT.")
                else:
                    agregar(data_dir, "proveedores", {
                        "nombre": nombre.strip(), "nit": nit.strip(), "categoria": categoria, "contacto": contacto.strip(),
                        "telefono": telefono.strip(), "email": email.strip(), "productos_servicios": productos.strip(), "estado": "Activo",
                    })
                    st.success("Proveedor registrado.")
                    st.rerun()

    if not proveedores.empty:
        with st.expander("🔄 Activar o inactivar proveedor"):
            with st.form("form_estado_proveedor"):
                p1, p2 = st.columns(2)
                nombre_sel = p1.selectbox("Proveedor", proveedores["nombre"].tolist())
                estado = p2.selectbox("Estado", ["Activo", "Inactivo"])
                if st.form_submit_button("Actualizar"):
                    proveedores.loc[proveedores["nombre"] == nombre_sel, "estado"] = estado
                    guardar(data_dir, "proveedores", proveedores)
                    st.success(f"{nombre_sel} quedó {estado}.")
                    st.rerun()
    editor(
        data_dir, "proveedores",
        {
            "nombre": "Proveedor", "nit": "NIT", "categoria": "Categoría", "contacto": "Contacto", "telefono": "Teléfono",
            "email": "Correo", "productos_servicios": "Productos / servicios", "estado": "Estado",
        },
        opciones={"categoria": CATEGORIAS_PROVEEDOR, "estado": ["Activo", "Inactivo"]},
        clave="nombre",
    )


PREGUNTAS_SUGERIDAS = [
    "Dame un resumen del estado actual de la central",
    "¿Qué sets están vencidos o por vencer y qué debo hacer?",
    "¿Qué insumos debo pedir y a qué proveedor?",
    "¿Qué cargas están pendientes o fueron rechazadas y por qué?",
    "¿Qué equipos necesitan mantenimiento?",
]


def contexto_ia(data_dir: str) -> str:
    instrumental = cargar(data_dir, "instrumental")
    instrumental.loc[sets_vencidos(instrumental), "estado"] = "Vencido"
    insumos = cargar(data_dir, "insumos")
    insumos["alerta"] = "Al día"
    insumos.loc[numeros(insumos["stock"]) <= numeros(insumos["stock_minimo"]), "alerta"] = "Bajo mínimo"
    insumos.loc[fechas(insumos["fecha_vencimiento"]) < date.today(), "alerta"] = "Vencido"
    tablas = {
        "INSTRUMENTAL Y SETS": instrumental,
        "CARGAS DE ESTERILIZACIÓN (últimas 60)": cargar(data_dir, "cargas").tail(60),
        "DESPACHOS Y RECEPCIONES (últimos 60)": cargar(data_dir, "despachos").tail(60),
        "INSUMOS": insumos,
        "MOVIMIENTOS DE INSUMOS (últimos 60)": cargar(data_dir, "movimientos_insumos").tail(60),
        "EQUIPOS": cargar(data_dir, "equipos"),
        "PROVEEDORES": cargar(data_dir, "proveedores"),
    }
    partes = [
        f"Fecha de hoy: {date.today().isoformat()}",
        "Vida útil por tipo de empaque (días): " + ", ".join(f"{k}: {v}" for k, v in VIDA_UTIL_EMPAQUE.items()),
        "Reglas: una carga se libera con indicador químico correcto y biológico negativo o no aplicable; "
        "biológico pendiente o implantes sin biológico negativo la dejan en cuarentena; Bowie-Dick fallido, "
        "viraje incorrecto o biológico positivo la rechazan. Un set con estado Vencido no se puede despachar.",
        f"Se alerta un set cuando vence en {DIAS_ALERTA_VENCIMIENTO} días o menos y un equipo cuando su mantenimiento es en {DIAS_ALERTA_MANTENIMIENTO} días o menos.",
    ]
    equipos = tablas["EQUIPOS"]
    mtto = equipos[(fechas(equipos["proximo_mantenimiento"]) <= date.today() + timedelta(days=DIAS_ALERTA_MANTENIMIENTO)) & (equipos["estado"] != "Fuera de servicio")]
    cargas = tablas["CARGAS DE ESTERILIZACIÓN (últimas 60)"]
    partes.append("## ALERTAS ACTIVAS (ya calculadas; úselas como fuente principal)\n" + "\n".join([
        "Sets vencidos (deben reprocesarse: lavado, empaque y nueva carga; no se desechan): " + (", ".join(instrumental.loc[instrumental["estado"] == "Vencido", "codigo"]) or "ninguno"),
        "Sets por vencer: " + (", ".join(instrumental.loc[sets_por_vencer(instrumental), "codigo"]) or "ninguno"),
        "Cargas en cuarentena: " + (", ".join(cargas.loc[cargas["resultado"] == "En cuarentena", "id"]) or "ninguna"),
        "Insumos bajo mínimo (pedir): " + (", ".join(insumos.loc[insumos["alerta"] == "Bajo mínimo", "nombre"]) or "ninguno"),
        "Insumos vencidos (retirar y reponer): " + (", ".join(insumos.loc[insumos["alerta"] == "Vencido", "nombre"]) or "ninguno"),
        "Equipos con mantenimiento vencido o próximo: " + (", ".join(mtto["nombre"] + " (" + mtto["proximo_mantenimiento"] + ")") or "ninguno"),
    ]))
    for titulo, df in tablas.items():
        partes.append(f"## {titulo} ({len(df)} registros)\n" + (df.to_csv(index=False) if not df.empty else "Sin registros."))
    return "\n\n".join(partes)


def render_ia(data_dir: str):
    st.subheader("🤖 Asistente IA de la central")
    st.caption("Responde con los datos actuales de inventario, cargas, despachos, insumos, equipos y proveedores. Solo consulta: no modifica registros.")

    try:
        asistente = ClinicalAIAssistant()
    except ValueError:
        st.warning("El asistente no está disponible: falta configurar la API Key de Groq en .streamlit/secrets.toml.")
        return

    chat = st.session_state.setdefault("chat_esterilizacion", [])
    pregunta = None
    sugerida = st.pills("Preguntas rápidas", PREGUNTAS_SUGERIDAS, key=f"sugerida_ia_{len(chat)}")
    for mensaje in chat:
        with st.chat_message(mensaje["role"]):
            st.markdown(mensaje["content"])

    escrita = st.chat_input("Pregunte sobre la central de esterilización…", key="chat_input_esterilizacion")
    pregunta = escrita or sugerida
    if chat and st.button("🗑️ Limpiar conversación"):
        st.session_state["chat_esterilizacion"] = []
        st.rerun()

    if pregunta:
        with st.chat_message("user"):
            st.markdown(pregunta)
        chat.append({"role": "user", "content": pregunta})
        with st.spinner("Consultando los datos de la central…"):
            resultado = asistente.ask_central_esterilizacion(contexto_ia(data_dir), chat[-8:])
        if resultado.get("error"):
            chat.pop()
            st.error(resultado["error"])
        else:
            chat.append({"role": "assistant", "content": resultado["response"]})
            st.rerun()


def render_esterilizacion(data_dir: str = "data"):
    st.title("🧼 Central de Esterilización")
    if st.session_state.get("rol") != ROL_ADMIN:
        st.error("Solo el administrador puede acceder a la Central de Esterilización.")
        return
    tabs = st.tabs(["📊 Panel", "📦 Inventario", "♨️ Cargas", "🚚 Despacho y recepción", "🧴 Insumos", "⚙️ Equipos", "🏢 Proveedores", "🤖 Asistente IA"])
    secciones = [render_panel, render_inventario, render_cargas, render_despachos, render_insumos, render_equipos, render_proveedores, render_ia]
    for tab, seccion in zip(tabs, secciones):
        with tab:
            seccion(data_dir)
