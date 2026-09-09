"""Autenticación y permisos.

Los usuarios viven en la tabla `usuarios` de Supabase (ver `usuarios.py`), no en
el código: así el admin puede darlos de alta desde la app. Las contraseñas se
guardan hasheadas, nunca en claro.

Regla de permisos: todos VEN todas las secciones. Los flags `edit_*`
controlan únicamente la EDICIÓN (registrar / eliminar) por sección.

Dos excepciones a esa regla:
  · En Seguimiento, `edit_seguimiento` además habilita LEER las respuestas
    textuales, que son confidenciales. Por eso las gerencias entran con el flag
    en False: ven los índices, los cortes y las alertas, pero no el textual
    crudo que el conductor dio bajo promesa de confidencialidad.
  · `es_admin` es el único permiso de LECTURA: habilita la auditoría y la
    administración de usuarios. No da permisos de edición sobre los datos —
    administrar y operar se mantienen separados.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import streamlit as st

import auditoria
import usuarios as us

# ─── Usuarios y permisos ─────────────────────────────────────
# La tabla se consulta seguido (cada rerun pregunta permisos), así que se
# cachea unos segundos. TTL corto a propósito: cuando el admin le saca un
# permiso a alguien, el cambio tiene que llegar rápido, no en la próxima sesión.
@st.cache_data(ttl=30, show_spinner=False)
def _usuario_cacheado(username: str):
    return us.buscar(username)


def invalidar_cache_usuarios() -> None:
    """Tras tocar un usuario: que el próximo run lea la tabla, no la caché."""
    _usuario_cacheado.clear()


# Alias interno: el resto de este módulo la llamaba así.
_invalidar_cache_usuarios = invalidar_cache_usuarios


def existe_usuario(username: str) -> bool:
    """True si el usuario existe y está activo (lo usa la cookie al restaurar)."""
    u = _usuario_cacheado((username or "").strip().lower())
    return bool(u and u.get("activo"))


COLOR_PRIMARY = "#ED5D3B"
COLOR_TEXT    = "#333333"
COLOR_BG      = "#EDEDED"


def _valid(username: str, password: str):
    """(ok, motivo). El motivo va a la auditoría, no a la pantalla."""
    u, motivo = us.validar_credenciales(username, password)
    return (u is not None), motivo


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
    """Llave HMAC para firmar la cookie de sesión.

    Sale de AUTH_SECRET si está definido; si no, se deriva de la SUPABASE_KEY.
    Antes se derivaba de las contraseñas de secrets, pero esas se mudaron a la
    base: si el fallback quedara vacío la llave sería una constante conocida y
    cualquiera podría firmarse una cookie `auth_user=admin`. Por eso, sin
    ninguno de los dos secretos, se corta.

    La SUPABASE_KEY es estable entre reinicios, así que las sesiones sobreviven
    los deploys; cambiarla invalida las cookies y todos re-loguean una vez.
    """
    raw = st.secrets.get("AUTH_SECRET") or st.secrets.get("SUPABASE_KEY")
    if not raw:
        raise RuntimeError(
            "Falta AUTH_SECRET (o SUPABASE_KEY) en secrets: sin un secreto "
            "estable no se puede firmar la cookie de sesión.")
    return hashlib.sha256(b"rot_auth_v2|" + str(raw).encode()).digest()


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
    return username if existe_usuario(username) else None


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
            ok, motivo = _valid(username, password)
            # Se audita el intento, salga bien o mal: una racha de fallidos
            # contra un usuario es justamente lo que un control debe mostrar.
            auditoria.registrar_login(username, ok, motivo)
            if ok:
                _invalidar_cache_usuarios()
                st.session_state["auth_user"] = username
                us.marcar_acceso(username)
                # Se escribe la cookie en el próximo run (ver require_login),
                # no acá: un st.rerun() inmediato cortaría el JS del componente.
                st.session_state["_auth_set_cookie"] = username
                st.rerun()
            else:
                # Mismo mensaje para los tres motivos: distinguir "no existe" de
                # "contraseña incorrecta" le confirma medio dato a quien prueba.
                st.error("Usuario o contraseña incorrectos.")


def _render_cambio_password(username: str) -> None:
    """Pantalla que bloquea la app hasta que el usuario fija su contraseña.

    Se muestra cuando `debe_cambiar_password` está en True: al crear la cuenta y
    cada vez que el admin resetea la clave. Quien la fijó la conoce, así que la
    cuenta no prueba identidad hasta que el dueño la cambia.
    """
    st.markdown(f"""
    <style>
    .stApp {{ background-color: {COLOR_BG}; }}
    [data-testid="stSidebar"] {{ display: none; }}
    .login-head {{ text-align: center; margin: 1rem 0 0.25rem; }}
    .login-head h1 {{ font-size: 1.4rem; font-weight: 700; color: #1a1a1a; margin: 0; }}
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
          <h1>Eleg&iacute; tu contrase&ntilde;a</h1>
          <p>Es tu primer ingreso (o te la resetearon). Nadie m&aacute;s va a conocerla.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("form_cambio_pass"):
            p1 = st.text_input("Contraseña nueva", type="password")
            p2 = st.text_input("Repetila", type="password")
            guardar = st.form_submit_button("Guardar", use_container_width=True)

        if guardar:
            ok, error = us.validar_password(p1, p2)
            if not ok:
                st.error(error)
            else:
                try:
                    us.cambiar_password_propia(username, p1)
                except Exception:  # noqa: BLE001
                    st.error("No se pudo guardar la contraseña. Intentá de nuevo.")
                else:
                    _invalidar_cache_usuarios()
                    auditoria.registrar("sesion", "cambio",
                                        "Fijó su contraseña")
                    st.rerun()

        if st.button("Cerrar sesión", use_container_width=True, key="btn_salir_pass"):
            logout()
            st.rerun()


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
    if existe_usuario(st.session_state.get("auth_user", "")):
        _persist_pending_cookie()  # escribe la cookie si el login fue recién
        _exigir_password_propia()
        return

    # 3) Restaurar desde la cookie del navegador (sobrevive el refresh).
    user = _read_token(_cookie_token())
    if user and existe_usuario(user):
        st.session_state["auth_user"] = user
        _exigir_password_propia()
        return

    # 4) Sin sesión: mostrar login.
    _render_login()
    st.stop()


def _exigir_password_propia() -> None:
    """Corta la app si el usuario todavía no fijó su propia contraseña."""
    u = current_user() or {}
    if u.get("debe_cambiar_password"):
        _render_cambio_password(st.session_state.get("auth_user", ""))
        st.stop()


def current_user() -> dict | None:
    """Devuelve el dict del usuario logueado, o None."""
    return _usuario_cacheado(st.session_state.get("auth_user", "") or "")


def es_admin() -> bool:
    """True si el usuario administra la plataforma.

    Es el único permiso de LECTURA: habilita la auditoría y la administración de
    usuarios. No da permisos de edición sobre los datos — administrar y operar
    se mantienen separados.
    """
    u = current_user()
    return bool(u and u.get("es_admin"))


def puede_ver_auditoria() -> bool:
    """La auditoría es del admin y de nadie más."""
    return es_admin()


def can_edit(section: str) -> bool:
    """True si el usuario puede editar la sección.

    Secciones: 'adelantos' | 'descuentos' | 'seguimiento' | 'minutas'.
    Los permisos se administran desde la pestaña Usuarios (sólo el admin).
    Ser admin NO habilita editar datos: administrar y operar van separados.
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
    auditoria.registrar("sesion", "logout", "Cerró sesión")
    st.session_state.pop("auth_user", None)
    st.session_state["_auth_clear_cookie"] = True
