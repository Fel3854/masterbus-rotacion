"""Vista: Manual de Usuario — Grupo Master"""

import os
import streamlit as st

# ─── Encontrar la ruta del manual dinámicamente ──────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
# current_dir es .../ROTACION/automatizaciones/datos/dashboard_rotacion/pages
repo_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
manual_path = os.path.join(repo_root, "docs", "manual_usuario.md")

# ─── CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Fira+Code:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Fira Sans', sans-serif;
    color: #333333;
}
.stApp { background-color: #EDEDED; }

/* ── Header de página ── */
.page-title {
    display: flex; align-items: center; gap: 12px;
    padding: 0.5rem 0 0.25rem;
}
.page-title .accent-bar {
    width: 5px; height: 36px; background: #ED5D3B;
    border-radius: 3px; flex-shrink: 0;
}
.page-title h1 {
    font-size: 1.75rem; font-weight: 700; color: #1a1a1a;
    margin: 0; letter-spacing: -0.5px;
}
.page-subtitle {
    color: #666; font-size: 0.9rem; margin: 0 0 1.75rem 17px;
}

/* Contenedor del manual */
.manual-container {
    background: #fff; border-radius: 12px;
    border: 1px solid #e0e0e0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04);
    padding: 2.5rem;
    margin-bottom: 2rem;
    color: #333;
}
.manual-container h1, .manual-container h2, .manual-container h3 {
    color: #1a1a1a;
}
.manual-container h1 { font-size: 1.8rem; margin-bottom: 1.5rem; border-bottom: 2px solid #ED5D3B; padding-bottom: 0.5rem;}
.manual-container h2 { font-size: 1.4rem; margin-top: 1.5rem; margin-bottom: 1rem; color: #ED5D3B; }
.manual-container h3 { font-size: 1.1rem; margin-top: 1.2rem; }
.manual-container p, .manual-container li { line-height: 1.6; font-size: 0.95rem; }
.manual-container hr { margin: 2rem 0; border-color: #e8e8e8; }
</style>
""", unsafe_allow_html=True)

# ─── Header ──────────────────────────────────────────────────
st.markdown("""
<div class="page-title">
  <div class="accent-bar"></div>
  <h1>Manual de Usuario</h1>
</div>
<p class="page-subtitle">Guía de uso y buenas prácticas para la plataforma de RRHH.</p>
""", unsafe_allow_html=True)

# ─── Renderizar el Markdown ──────────────────────────────────
if os.path.exists(manual_path):
    with open(manual_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    st.markdown('<div class="manual-container">', unsafe_allow_html=True)
    st.markdown(content)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    # Si no se encuentra el archivo físico (por ejemplo, si se deploya mal en la nube), mostramos una alerta.
    st.error(f"No se pudo cargar el archivo del manual. Ruta buscada: `{manual_path}`")
    st.info("Por favor, contacta con soporte para revisar la configuración del servidor.")

