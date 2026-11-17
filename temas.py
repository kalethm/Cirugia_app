import streamlit as st
from streamlit import config

TEMAS = {
    "Claro": {"base": "light", "primaryColor": "#0B5ED7", "backgroundColor": "#FFFFFF", "secondaryBackgroundColor": "#F0F2F6", "textColor": "#262730"},
    "Oscuro": {"base": "dark", "primaryColor": "#4DA3FF", "backgroundColor": "#0E1117", "secondaryBackgroundColor": "#262730", "textColor": "#FAFAFA"},
    "Verde": {"base": "light", "primaryColor": "#1B7F4B", "backgroundColor": "#F4FBF6", "secondaryBackgroundColor": "#DCEFE3", "textColor": "#12301F"},
    "Azul": {"base": "light", "primaryColor": "#0B5ED7", "backgroundColor": "#F3F8FF", "secondaryBackgroundColor": "#D9E8FB", "textColor": "#0B2545"},
}
ICONOS = {"Claro": "☀️", "Oscuro": "🌙", "Verde": "🟢", "Azul": "🔵"}


def aplicar_tema():
    tema = TEMAS[st.session_state.setdefault("tema", "Claro")]
    if any(config.get_option(f"theme.{k}") != v for k, v in tema.items()):
        for k, v in tema.items():
            config.set_option(f"theme.{k}", v)
        st.rerun()


def selector_tema():
    with st.sidebar.expander("🎨 Personalización", expanded=True):
        columnas = st.columns(2)
        for i, nombre in enumerate(TEMAS):
            if columnas[i % 2].button(f"{ICONOS[nombre]} {nombre}", key=f"tema__{nombre}", type="primary" if nombre == st.session_state["tema"] else "secondary", width="stretch"):
                st.session_state["tema"] = nombre
                st.rerun()
