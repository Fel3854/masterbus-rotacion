#!/usr/bin/env python3
"""Entry point — Dashboard Rotación de Personal, Grupo Master"""

import logging
import streamlit as st

from auth import require_login, current_user, logout, es_admin

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

st.set_page_config(
    page_title="Rotación — Grupo Master",
    page_icon="📊",
    layout="wide",
)

# ─── Puerta de login (protege todas las páginas) ─────────────
require_login()

paginas = [
    st.Page("_dashboard.py",                        title="Dashboard",           icon="📊"),
    st.Page("pages/1_Adelantos_de_Sueldo.py",       title="Adelantos de Sueldo", icon="💵"),
    st.Page("pages/2_Descuentos.py",                title="Descuentos",          icon="📋"),
    st.Page("pages/3_Vencimientos.py",              title="Vencimientos",        icon="⏳"),
    st.Page("pages/5_Seguimiento.py",               title="Seguimiento",         icon="🧭"),
    st.Page("pages/6_Minutas.py",                   title="Minutas Reunión",     icon="📝"),
]

# Auditoría y Usuarios son del admin. Esconderlas del menú no alcanza como
# control: cada página vuelve a chequear el permiso por su cuenta.
if es_admin():
    paginas.append(
        st.Page("pages/7_Auditoria.py",             title="Auditoría",           icon="🔎"))
    paginas.append(
        st.Page("pages/8_Usuarios.py",              title="Usuarios",            icon="👥"))

paginas.append(
    st.Page("pages/4_Manual_de_Usuario.py",         title="Manual de Usuario",   icon="📖"))

pg = st.navigation(paginas)

# ─── Usuario activo + cerrar sesión (en todas las páginas) ───
with st.sidebar:
    st.caption(f"Sesión: {(current_user() or {}).get('nombre', '')}")
    if st.button("Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()

pg.run()
