#!/usr/bin/env python3
"""Entry point — Dashboard Rotación de Personal, Grupo Master"""

import streamlit as st

st.set_page_config(
    page_title="Rotación — Grupo Master",
    page_icon="📊",
    layout="wide",
)

pg = st.navigation([
    st.Page("_dashboard.py",                        title="Dashboard",           icon="📊"),
    st.Page("pages/1_Adelantos_de_Sueldo.py",       title="Adelantos de Sueldo", icon="💵"),
    st.Page("pages/2_Descuentos.py",                title="Descuentos",          icon="📋"),
    st.Page("pages/3_Vencimientos.py",              title="Vencimientos",        icon="⏳"),
    st.Page("pages/4_Manual_de_Usuario.py",         title="Manual de Usuario",   icon="📖"),
])
pg.run()
