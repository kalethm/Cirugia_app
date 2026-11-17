import streamlit as st


def botones_nav(opciones, clave, contenedor=None, horizontal=False, etiquetas=None, titulo=None):
    contenedor = contenedor or st
    etiquetas = etiquetas or {}
    if st.session_state.get(clave) not in opciones:
        st.session_state[clave] = opciones[0]
    actual = st.session_state[clave]
    if titulo:
        contenedor.caption(titulo)
    destinos = contenedor.columns(len(opciones)) if horizontal else [contenedor] * len(opciones)
    for destino, opcion in zip(destinos, opciones):
        if destino.button(etiquetas.get(opcion, opcion), key=f"{clave}__{opcion}", type="primary" if opcion == actual else "secondary", width="stretch"):
            st.session_state[clave] = opcion
            st.rerun()
    return actual
