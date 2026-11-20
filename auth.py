import streamlit as st
import pandas as pd
import db

def cargar_usuarios():
    return db.leer("usuarios")

def login():
    st.title("🔐 Sistema de Gestión de Cirugías")
    st.subheader("Inicio de sesión")

    usuario = st.text_input("Usuario")
    clave = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        usuarios = cargar_usuarios()

        validado = usuarios[
            (usuarios["usuario"] == usuario) &
            (usuarios["clave"] == clave)
        ]

        if not validado.empty:
            st.session_state["autenticado"] = True
            st.session_state["usuario"] = usuario
            st.session_state["rol"] = validado.iloc[0]["rol"]
            st.success("Acceso concedido")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")
