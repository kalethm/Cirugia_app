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
        nombres = list(TEMAS)
        elegido = st.radio("Tema", nombres, index=nombres.index(st.session_state["tema"]), format_func=lambda t: f"{ICONOS[t]} {t}", horizontal=True)
    if elegido != st.session_state["tema"]:
        st.session_state["tema"] = elegido
        st.rerun()
