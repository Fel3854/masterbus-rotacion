"""Autenticación y permisos — usuarios de configuración fija.

Los 3 usuarios y sus permisos de edición se definen acá (config fija).
Las contraseñas NO viven en el código: se leen de `st.secrets["passwords"]`
(archivo .streamlit/secrets.toml, que no se versiona).

Regla de permisos: todos VEN todas las secciones. Los flags `edit_*`
controlan únicamente la EDICIÓN (registrar / eliminar) por sección.
"""

from __future__ import annotations

import streamlit as st

# ─── Usuarios y permisos ─────────────────────────────────────
USERS = {
    "lu":     {"name": "Lu",     "edit_adelantos": True,  "edit_descuentos": False},
    "victor": {"name": "Victor", "edit_adelantos": False, "edit_descuentos": True},
    "flor":   {"name": "Flor",   "edit_adelantos": True,  "edit_descuentos": True},
}

COLOR_PRIMARY = "#ED5D3B"
COLOR_TEXT    = "#333333"
COLOR_BG      = "#EDEDED"


def _valid(username: str, password: str) -> bool:
    """True si el usuario existe y la contraseña coincide con la de secrets."""
    if username not in USERS:
        return False
    passwords = st.secrets.get("passwords", {})
    return bool(password) and passwords.get(username) == password


def _render_login() -> None:
    """Dibuja el formulario de login centrado."""
    st.markdown(f"""
    <style>
    .stApp {{ background-color: {COLOR_BG}; }}
    [data-testid="stSidebar"] {{ display: none; }}
    .login-head {{
        text-align: center; margin: 1rem 0 0.25rem;
    }}
    .login-head h1 {{
        font-size: 1.6rem; font-weight: 700; color: #1a1a1a; margin: 0;
    }}
    .login-head p {{ color: #666; font-size: 0.9rem; margin-top: 0.25rem; }}
    .login-bar {{
        width: 56px; height: 5px; background: {COLOR_PRIMARY};
        border-radius: 3px; margin: 0 auto 0.75rem;
    }}
    </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div class="login-head">
          <div class="login-bar"></div>
          <h1>Rotación — Grupo Master</h1>
          <p>Ingresá con tu usuario y contraseña.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("form_login"):
            username = st.text_input("Usuario").strip().lower()
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", use_container_width=True)

        if submitted:
            if _valid(username, password):
                st.session_state["auth_user"] = username
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")


def require_login() -> None:
    """Si no hay sesión activa, muestra el login y detiene el render de la app."""
    if st.session_state.get("auth_user") in USERS:
        return
    _render_login()
    st.stop()


def current_user() -> dict | None:
    """Devuelve el dict del usuario logueado, o None."""
    return USERS.get(st.session_state.get("auth_user", ""))


def can_edit(section: str) -> bool:
    """True si el usuario logueado puede editar la sección ('adelantos' | 'descuentos')."""
    u = current_user()
    return bool(u and u.get(f"edit_{section}"))


def logout() -> None:
    """Cierra la sesión actual."""
    st.session_state.pop("auth_user", None)
