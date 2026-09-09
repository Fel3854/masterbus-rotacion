"""Autenticación y permisos — usuarios de configuración fija.

Los 3 usuarios y sus permisos de edición se definen acá (config fija).
Las contraseñas NO viven en el código: se leen de `st.secrets["passwords"]`
(archivo .streamlit/secrets.toml, que no se versiona).

Regla de permisos: todos VEN todas las secciones. Los flags `edit_*`
controlan únicamente la EDICIÓN (registrar / eliminar) por sección.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import streamlit as st

# ─── Usuarios y permisos ─────────────────────────────────────
USERS = {
    "lu":      {"name": "Lu",      "edit_adelantos": True,  "edit_descuentos": True,  "edit_seguimiento": True,  "edit_minutas": True},
    "victor":  {"name": "Victor",  "edit_adelantos": False, "edit_descuentos": True,  "edit_seguimiento": False, "edit_minutas": False},
    "flor":    {"name": "Flor",    "edit_adelantos": True,  "edit_descuentos": True,  "edit_seguimiento": True,  "edit_minutas": True},
    "sueldos": {"name": "Sueldos", "edit_adelantos": False, "edit_descuentos": False, "edit_seguimiento": False, "edit_minutas": False},
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


# ─── Persistencia de sesión en el navegador (cookie firmada) ─────────
# Por defecto Streamlit ata el login a `st.session_state`, que vive en la
# conexión de la pestaña: al refrescar (F5) la sesión se rearma vacía y vuelve
# a pedir login. Para que sobreviva el refresh guardamos una cookie con un token
# FIRMADO (HMAC): usuario + vencimiento + firma. Sin la firma, cualquiera pondría
# una cookie `auth_user=lu` y entraría sin contraseña; con HMAC la cookie no se
# puede falsificar. La llave se deriva de las contraseñas de secrets, así que no
# hace falta configurar ningún secreto nuevo (ni en local ni en Streamlit Cloud).
#
# Es una cookie de SESIÓN (sin expiración en el navegador): sobrevive el refresh
# y se borra al cerrar el navegador. El token igual lleva un tope de seguridad
# por si el navegador restaura la pestaña tras estar días cerrado.
_COOKIE_NAME = "rot_sess"
_TOKEN_MAX_SEG = 16 * 3600  # tope duro del token: cubre una jornada larga.


def _cookie_controller():
    """Controlador de cookies (import perezoso).

    Si la dependencia `streamlit-cookies-controller` no está instalada, devuelve
    None y el login sigue funcionando igual, sólo que sin persistir el refresh
    (degradación elegante: la app nunca se cae por esto).
    """
    try:
        from streamlit_cookies_controller import CookieController
    except Exception:
        return None
    return CookieController(key="rot_cookie_ctrl")


def _signing_key() -> bytes:
    """Llave HMAC derivada de las contraseñas de secrets.

    Es un secreto ya existente y estable entre reinicios, así que sirve para
    firmar sin agregar configuración. Si se cambian las contraseñas, las cookies
    viejas quedan inválidas y se vuelve a pedir login una vez (aceptable).
    """
    pw = st.secrets.get("passwords", {})
    raw = "|".join(f"{k}={pw[k]}" for k in sorted(pw)).encode()
    return hashlib.sha256(b"rot_auth_v1|" + raw).digest()


def _make_token(username: str) -> str:
    """Token firmado `usuario.vencimiento.firma` para guardar en la cookie."""
    exp = int(time.time()) + _TOKEN_MAX_SEG
    msg = f"{username}.{exp}"
    sig = hmac.new(_signing_key(), msg.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{msg}.{sig}"


def _read_token(token) -> str | None:
    """Devuelve el usuario si el token es válido (firma OK y no vencido), o None."""
    if not token or not isinstance(token, str) or token.count(".") != 2:
        return None
    username, exp_s, sig = token.split(".")
    good = hmac.new(_signing_key(), f"{username}.{exp_s}".encode(),
                    hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, good):
        return None
    try:
        if int(exp_s) < int(time.time()):
            return None
    except ValueError:
        return None
    return username if username in USERS else None


def _cookie_token() -> str | None:
    """Lee el token de la cookie del request (nativo, sin parpadeo en el 1er run)."""
    try:
        return st.context.cookies.get(_COOKIE_NAME)
    except Exception:
        return None


def _persist_pending_cookie() -> None:
    """Escribe la cookie de sesión después de un login.

    Se llama en un run 'limpio' (sin `st.rerun()` inmediato después), para que el
    componente alcance a ejecutar el JS que setea la cookie. Sin `expires` ni
    `max_age` → cookie de sesión (se borra al cerrar el navegador).
    """
    u = st.session_state.pop("_auth_set_cookie", None)
    if not u:
        return
    c = _cookie_controller()
    if c is None:
        return
    try:
        c.set(_COOKIE_NAME, _make_token(u))
    except Exception:
        pass


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
                # Se escribe la cookie en el próximo run (ver require_login),
                # no acá: un st.rerun() inmediato cortaría el JS del componente.
                st.session_state["_auth_set_cookie"] = username
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")


def require_login() -> None:
    """Si no hay sesión activa, muestra el login y detiene el render de la app.

    Además persiste/restaura la sesión vía cookie firmada para que el refresh
    (F5) no obligue a re-loguearse (ver la sección de cookies arriba).
    """
    # 1) Logout pedido en el run anterior: borrar la cookie y NO restaurar.
    if st.session_state.pop("_auth_clear_cookie", False):
        c = _cookie_controller()
        if c is not None:
            try:
                c.remove(_COOKIE_NAME)
            except Exception:
                pass
        _render_login()
        st.stop()

    # 2) Sesión ya activa en esta pestaña.
    if st.session_state.get("auth_user") in USERS:
        _persist_pending_cookie()  # escribe la cookie si el login fue recién
        return

    # 3) Restaurar desde la cookie del navegador (sobrevive el refresh).
    user = _read_token(_cookie_token())
    if user in USERS:
        st.session_state["auth_user"] = user
        return

    # 4) Sin sesión: mostrar login.
    _render_login()
    st.stop()


def current_user() -> dict | None:
    """Devuelve el dict del usuario logueado, o None."""
    return USERS.get(st.session_state.get("auth_user", ""))


def can_edit(section: str) -> bool:
    """True si el usuario puede editar la sección.

    Secciones: 'adelantos' | 'descuentos' | 'seguimiento' | 'minutas'.
    Para sumar un usuario a una sección alcanza con poner su flag en True arriba.
    En Seguimiento este permiso además habilita ver las respuestas textuales
    (son confidenciales: el conductor las da bajo promesa de confidencialidad).
    """
    u = current_user()
    return bool(u and u.get(f"edit_{section}"))


def logout() -> None:
    """Cierra la sesión actual y marca la cookie para borrarse en el próximo run.

    El borrado real de la cookie lo hace require_login() en el run siguiente
    (tras el st.rerun() del botón), para que el componente alcance a correr.
    """
    st.session_state.pop("auth_user", None)
    st.session_state["_auth_clear_cookie"] = True
