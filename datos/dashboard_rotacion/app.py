#!/usr/bin/env python3
"""Entry point — Dashboard Rotación de Personal, Grupo Master"""

import logging
import streamlit as st

from auth import require_login, current_user, logout

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

pg = st.navigation([
    st.Page("_dashboard.py",                        title="Dashboard",           icon="📊"),
    st.Page("pages/1_Adelantos_de_Sueldo.py",       title="Adelantos de Sueldo", icon="💵"),
    st.Page("pages/2_Descuentos.py",                title="Descuentos",          icon="📋"),
    st.Page("pages/3_Vencimientos.py",              title="Vencimientos",        icon="⏳"),
    st.Page("pages/4_Manual_de_Usuario.py",         title="Manual de Usuario",   icon="📖"),
])

# ─── Usuario activo + cerrar sesión (en todas las páginas) ───
with st.sidebar:
    st.caption(f"Sesión: {(current_user() or {}).get('name', '')}")
    if st.button("Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()

pg.run()
