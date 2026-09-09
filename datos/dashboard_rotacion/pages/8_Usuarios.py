"""Vista: Usuarios — alta, permisos y contraseñas. Sólo el administrador."""

import html
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from auth import es_admin, current_user, invalidar_cache_usuarios  # noqa: E402
from utils import inyectar_css_base  # noqa: E402
import auditoria  # noqa: E402
import usuarios as us  # noqa: E402

_esc = html.escape

inyectar_css_base()
st.markdown("""
<style>
.u-row { border-left: 4px solid var(--acc, #ccc); padding: 8px 0 8px 12px; }
.u-nombre { font-size: 1rem; font-weight: 700; color: #1a1a1a; }
.u-user {
    font-family: 'Fira Code', monospace; font-size: 0.8rem; color: #777;
    margin-left: 8px;
}
.u-chip {
    display: inline-block; font-size: 0.64rem; font-weight: 800;
    padding: 2px 9px; border-radius: 11px; margin-left: 7px;
    text-transform: uppercase; letter-spacing: 0.4px;
    background: var(--chip, #888); color: #fff; vertical-align: middle;
}
.u-meta { font-size: 0.78rem; color: #777; margin-top: 3px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-title">
  <div class="accent-bar"></div>
  <h1>Usuarios</h1>
</div>
<p class="page-subtitle">Alta de usuarios, permisos por módulo y contraseñas.</p>
""", unsafe_allow_html=True)

# Está fuera de la navegación para quien no es admin, pero igual se corta acá:
# una URL directa no puede saltear el control.
if not es_admin():
    st.error("No tenés permiso para administrar usuarios.")
    st.stop()

YO = (st.session_state.get("auth_user") or "").strip().lower()
MI_NOMBRE = (current_user() or {}).get("nombre") or YO


@st.cache_data(ttl=30, show_spinner=False)
def _leer():
    return us.leer_usuarios()


def _refrescar():
    """Tras cualquier cambio: la lista y la caché de permisos quedan viejas."""
    _leer.clear()
    invalidar_cache_usuarios()


df = _leer()

tab_lista, tab_alta = st.tabs(["Usuarios", "Nuevo usuario"])

# ══════════════════════════════════════════════════════════════
# Lista y edición
# ══════════════════════════════════════════════════════════════
with tab_lista:
    if df.empty:
        st.info("Todavía no hay usuarios cargados.")
    else:
        activos = int(df["activo"].fillna(False).sum())
        admins = int((df["es_admin"].fillna(False) & df["activo"].fillna(False)).sum())
        st.caption(f"{len(df)} usuario(s) · {activos} activo(s) · {admins} administrador(es)")

        for _, u in df.iterrows():
            usuario = u["usuario"]
            es_yo = usuario == YO
            inactivo = not bool(u["activo"])
            acc = "#8C8987" if inactivo else ("#ED5D3B" if u["es_admin"] else "#46BCD2")

            chips = ""
            if u["es_admin"]:
                chips += '<span class="u-chip" style="--chip:#ED5D3B;">Admin</span>'
            if inactivo:
                chips += '<span class="u-chip" style="--chip:#D12F19;">Desactivado</span>'
            if u["debe_cambiar_password"]:
                chips += '<span class="u-chip" style="--chip:#B45309;">Debe fijar contraseña</span>'
            if es_yo:
                chips += '<span class="u-chip" style="--chip:#15803D;">Sos vos</span>'

            ult = u["ultimo_acceso"]
            ult_txt = "nunca ingresó"
            if pd.notna(ult):
                ult_txt = "último ingreso " + pd.to_datetime(ult, utc=True) \
                    .tz_convert("America/Argentina/Buenos_Aires").strftime("%d/%m/%Y %H:%M")

            with st.container(border=True):
                st.markdown(
                    f'<div class="u-row" style="--acc:{acc};">'
                    f'<div><span class="u-nombre">{_esc(str(u["nombre"]))}</span>'
                    f'<span class="u-user">{_esc(usuario)}</span>{chips}</div>'
                    f'<div class="u-meta">{_esc(us.resumen_permisos(u))} · {ult_txt}</div>'
                    f'</div>', unsafe_allow_html=True)

                with st.expander("Editar"):
                    with st.form(f"form_edit_{usuario}"):
                        nombre = st.text_input("Nombre visible", value=str(u["nombre"]),
                                               key=f"nom_{usuario}")
                        st.caption("Permisos de edición (todos ven todas las secciones)")
                        marcas = {}
                        for clave, label, desc in us.PERMISOS:
                            marcas[clave] = st.checkbox(
                                label, value=bool(u[clave]), help=desc,
                                key=f"{clave}_{usuario}")
                        admin_nuevo = st.checkbox(
                            "Administrador", value=bool(u["es_admin"]),
                            help="Ve la auditoría y administra usuarios. No habilita editar datos.",
                            key=f"adm_{usuario}")
                        guardar = st.form_submit_button("Guardar cambios")

                    if guardar:
                        # Sacarle el admin al último administrador activo deja la
                        # administración inaccesible desde la app.
                        quita_admin = bool(u["es_admin"]) and not admin_nuevo
                        if quita_admin and us.otros_admins_activos(df, usuario) == 0:
                            st.error("No podés quitar el último administrador activo. "
                                     "Nombrá otro admin primero.")
                        elif not nombre.strip():
                            st.error("El nombre visible no puede quedar vacío.")
                        else:
                            try:
                                if nombre.strip() != str(u["nombre"]):
                                    us.actualizar_nombre(usuario, nombre)
                                us.actualizar_permisos(usuario, marcas, es_admin=admin_nuevo)
                            except Exception:  # noqa: BLE001
                                st.error("No se pudo guardar. Intentá de nuevo.")
                            else:
                                fila = dict(marcas, es_admin=admin_nuevo)
                                auditoria.registrar(
                                    "usuarios", "cambio",
                                    f"{nombre.strip()} ({usuario}) → {us.resumen_permisos(fila)}",
                                    registro_id=usuario, datos=fila)
                                _refrescar()
                                st.toast("Usuario actualizado.", icon="✅")
                                st.rerun()

                    st.divider()
                    c_pass, c_estado = st.columns(2)

                    # ── Resetear contraseña ──
                    with c_pass:
                        with st.form(f"form_pass_{usuario}"):
                            st.caption("Resetear contraseña")
                            nueva = st.text_input(
                                "Contraseña provisoria", type="password",
                                key=f"pass_{usuario}",
                                help="Se la pasás por otro medio. En su próximo "
                                     "ingreso la app le va a exigir cambiarla.")
                            resetear = st.form_submit_button("Resetear")
                        if resetear:
                            ok, error = us.validar_password(nueva)
                            if not ok:
                                st.error(error)
                            else:
                                try:
                                    us.resetear_password(usuario, nueva)
                                except Exception:  # noqa: BLE001
                                    st.error("No se pudo resetear la contraseña.")
                                else:
                                    auditoria.registrar(
                                        "usuarios", "cambio",
                                        f"Reseteó la contraseña de {u['nombre']} ({usuario})",
                                        registro_id=usuario)
                                    _refrescar()
                                    st.toast("Contraseña reseteada.", icon="🔑")
                                    st.rerun()

                    # ── Activar / desactivar ──
                    with c_estado:
                        st.caption("Estado de la cuenta")
                        if es_yo:
                            st.caption("No podés desactivar tu propia cuenta.")
                        elif inactivo:
                            if st.button("Reactivar", key=f"act_{usuario}",
                                         use_container_width=True):
                                us.set_activo(usuario, True)
                                auditoria.registrar(
                                    "usuarios", "cambio",
                                    f"Reactivó a {u['nombre']} ({usuario})",
                                    registro_id=usuario)
                                _refrescar()
                                st.rerun()
                        else:
                            ultimo_admin = (bool(u["es_admin"])
                                            and us.otros_admins_activos(df, usuario) == 0)
                            if ultimo_admin:
                                st.caption("Es el último administrador activo: "
                                           "nombrá otro antes de desactivarlo.")
                            elif st.button("Desactivar", key=f"des_{usuario}",
                                           use_container_width=True):
                                # No se borra la fila: la auditoría referencia a
                                # este usuario y su historial tiene que seguir
                                # siendo legible.
                                us.set_activo(usuario, False)
                                auditoria.registrar(
                                    "usuarios", "baja",
                                    f"Desactivó a {u['nombre']} ({usuario})",
                                    registro_id=usuario)
                                _refrescar()
                                st.rerun()

# ══════════════════════════════════════════════════════════════
# Alta
# ══════════════════════════════════════════════════════════════
with tab_alta:
    with st.form("form_alta_usuario", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            nuevo_usuario = st.text_input(
                "Usuario *", placeholder="ej: jperez",
                help="Minúsculas, 3 a 20 caracteres. Es con lo que va a entrar.")
        with c2:
            nuevo_nombre = st.text_input(
                "Nombre visible *", placeholder="ej: Juan Pérez — Supervisor")

        nueva_pass = st.text_input(
            "Contraseña provisoria *", type="password",
            help="Se la pasás por otro medio. En su primer ingreso la app le "
                 "va a exigir que la cambie por una que sólo conozca él.")

        st.caption("Permisos de edición (todos ven todas las secciones)")
        marcas_nuevas = {}
        for clave, label, desc in us.PERMISOS:
            marcas_nuevas[clave] = st.checkbox(label, value=False, help=desc,
                                               key=f"nuevo_{clave}")
        nuevo_admin = st.checkbox(
            "Administrador", value=False, key="nuevo_admin",
            help="Ve la auditoría y administra usuarios. No habilita editar datos.")

        crear = st.form_submit_button("Crear usuario")

    if crear:
        errores = []
        ok_u, err_u = us.validar_usuario(nuevo_usuario)
        if not ok_u:
            errores.append(err_u)
        if not (nuevo_nombre or "").strip():
            errores.append("Poné un nombre visible.")
        ok_p, err_p = us.validar_password(nueva_pass)
        if not ok_p:
            errores.append(err_p)
        if not df.empty and (nuevo_usuario or "").strip().lower() in set(df["usuario"]):
            errores.append("Ya existe un usuario con ese nombre.")

        if errores:
            st.error("\n\n".join(f"- {e}" for e in errores))
        else:
            try:
                us.crear(nuevo_usuario, nuevo_nombre, nueva_pass,
                         marcas_nuevas, es_admin=nuevo_admin, creado_por=MI_NOMBRE)
            except Exception as e:  # noqa: BLE001
                if "duplicate key" in str(e).lower() or "23505" in str(e):
                    st.error("Ya existe un usuario con ese nombre.")
                else:
                    st.error("No se pudo crear el usuario. Intentá de nuevo.")
            else:
                fila = dict(marcas_nuevas, es_admin=nuevo_admin)
                auditoria.registrar(
                    "usuarios", "alta",
                    f"{nuevo_nombre.strip()} ({nuevo_usuario.strip().lower()}) "
                    f"→ {us.resumen_permisos(fila)}",
                    registro_id=nuevo_usuario.strip().lower(), datos=fila)
                _refrescar()
                st.success(
                    f"✓ Usuario **{nuevo_usuario.strip().lower()}** creado. "
                    "Pasale la contraseña provisoria por otro medio: en su primer "
                    "ingreso la app le va a pedir que la cambie.")
