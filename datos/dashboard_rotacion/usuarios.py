"""Usuarios del dashboard — alta, permisos y contraseñas.

Hasta acá los usuarios vivían en un dict de `auth.py` y las contraseñas en
`secrets.toml`. Ahora viven en la tabla `usuarios`, porque un admin no puede
editar el código de la app desde la app: para dar de alta a alguien sin tocar el
repo, los usuarios tienen que ser datos.

Las contraseñas se guardan **hasheadas** (PBKDF2-HMAC-SHA256 con salt por
usuario), nunca en claro. Nadie —ni el admin— puede leer la contraseña de otro:
sólo puede resetearla, y el dueño la vuelve a fijar en el primer ingreso.

El hash es de la biblioteca estándar a propósito: sumar `bcrypt` o `argon2` sería
mejor en teoría, pero agrega una dependencia compilada al deploy para proteger
siete cuentas internas. PBKDF2 con 400k iteraciones es defensa suficiente para
este caso y no agrega nada al `requirements.txt`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re

import pandas as pd

from utils import get_supabase

TABLA = "usuarios"

# ─── Hash de contraseñas ─────────────────────────────────────
ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 400_000     # ~85 ms por verificación: caro para fuerza bruta, imperceptible al entrar
LARGO_SALT = 16
LARGO_MINIMO_PASSWORD = 8

# Columnas que se leen para operar. `password_hash` NO está: se pide aparte y
# sólo al validar un login, para que el hash no ande dando vueltas en caches ni
# en los DataFrames de la pantalla de administración.
COLUMNAS = ["usuario", "nombre", "activo", "es_admin",
            "edit_adelantos", "edit_descuentos", "edit_seguimiento", "edit_minutas",
            "debe_cambiar_password", "fecha_alta", "creado_por", "ultimo_acceso"]

# ─── Catálogo de permisos ────────────────────────────────────
# Un solo lugar define los permisos: alimenta la pantalla de administración, el
# payload del alta y el texto que se escribe en la auditoría.
PERMISOS = [
    ("edit_adelantos",   "Adelantos de Sueldo",
     "Registrar y eliminar adelantos"),
    ("edit_descuentos",  "Descuentos",
     "Registrar y eliminar descuentos"),
    ("edit_seguimiento", "Seguimiento",
     "Cargar entrevistas y ver las respuestas textuales (confidenciales)"),
    ("edit_minutas",     "Minutas",
     "Crear, editar y eliminar minutas"),
]
CLAVES_PERMISO = [c for c, _l, _d in PERMISOS]


def hash_password(password):
    """Devuelve `algoritmo$iteraciones$salt$hash`, todo en base64."""
    salt = os.urandom(LARGO_SALT)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERACIONES)
    return "$".join([
        ALGORITMO, str(ITERACIONES),
        base64.b64encode(salt).decode(), base64.b64encode(dk).decode(),
    ])


def verificar_password(password, almacenado):
    """True si la contraseña coincide con el hash guardado.

    Lee las iteraciones del propio hash en vez de usar la constante: si mañana
    se sube el costo, las contraseñas viejas se siguen verificando con el valor
    con el que fueron creadas y nadie queda afuera.
    """
    if not password or not almacenado or not isinstance(almacenado, str):
        return False
    try:
        algoritmo, iteraciones, salt_b64, hash_b64 = almacenado.split("$")
        if algoritmo != ALGORITMO:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 base64.b64decode(salt_b64), int(iteraciones))
    except (ValueError, TypeError):
        return False
    # compare_digest y no ==: el == corta en el primer byte distinto y el tiempo
    # que tarda filtra información sobre el hash.
    return hmac.compare_digest(dk, base64.b64decode(hash_b64))


# ─── Validaciones ────────────────────────────────────────────
# Mínimo 2 y no 3: "lu" es un usuario real desde antes de esta tabla.
_RE_USUARIO = re.compile(r"^[a-z0-9_.]{2,20}$")


def validar_usuario(usuario):
    """(ok, mensaje de error). El nombre de usuario es la clave primaria."""
    u = (usuario or "").strip().lower()
    if not u:
        return False, "Poné un nombre de usuario."
    if not _RE_USUARIO.match(u):
        return False, ("El usuario va entre 2 y 20 caracteres y sólo admite "
                       "letras, números, punto y guión bajo. Se guarda en "
                       "minúsculas.")
    return True, ""


def validar_password(password, repetida=None):
    """(ok, mensaje de error)."""
    p = password or ""
    if len(p) < LARGO_MINIMO_PASSWORD:
        return False, f"La contraseña necesita al menos {LARGO_MINIMO_PASSWORD} caracteres."
    if p.strip() != p:
        return False, "La contraseña no puede empezar ni terminar con un espacio."
    if repetida is not None and p != repetida:
        return False, "Las dos contraseñas no coinciden."
    return True, ""


def resumen_permisos(fila):
    """Texto legible de lo que puede hacer un usuario. Va a la auditoría."""
    if fila.get("es_admin"):
        return "Administrador"
    puede = [label for clave, label, _d in PERMISOS if fila.get(clave)]
    return " · ".join(puede) if puede else "Solo lectura"


# ─── Acceso a datos ──────────────────────────────────────────
def leer_usuarios():
    """Todos los usuarios, sin el hash de contraseña."""
    resp = (get_supabase().table(TABLA).select(",".join(COLUMNAS))
            .order("usuario").execute())
    return pd.DataFrame(resp.data or [], columns=COLUMNAS)


def buscar(usuario):
    """Un usuario por su clave, sin el hash. None si no existe."""
    resp = (get_supabase().table(TABLA).select(",".join(COLUMNAS))
            .eq("usuario", (usuario or "").strip().lower()).limit(1).execute())
    return (resp.data or [None])[0]


def _hash_guardado(usuario):
    """El hash de un usuario. Sólo lo usa la validación del login."""
    resp = (get_supabase().table(TABLA).select("password_hash")
            .eq("usuario", (usuario or "").strip().lower()).limit(1).execute())
    return (resp.data or [{}])[0].get("password_hash")


def validar_credenciales(usuario, password):
    """(usuario_dict, motivo_del_rechazo).

    Devuelve el dict sólo si el usuario existe, está activo y la contraseña
    coincide. El motivo es para la auditoría, NO para mostrarle al que intenta
    entrar: decirle "el usuario existe pero la contraseña está mal" le confirma
    medio dato.
    """
    u = buscar(usuario)
    if not u:
        return None, "usuario inexistente"
    if not u.get("activo"):
        return None, "usuario desactivado"
    if not verificar_password(password, _hash_guardado(usuario)):
        return None, "contraseña incorrecta"
    return u, ""


def crear(usuario, nombre, password, permisos, es_admin=False, creado_por=None):
    """Alta. El usuario entra con `debe_cambiar_password` en True."""
    fila = {
        "usuario": usuario.strip().lower(),
        "nombre": nombre.strip(),
        "activo": True,
        "es_admin": bool(es_admin),
        "password_hash": hash_password(password),
        # Quien crea la cuenta conoce la contraseña inicial: no sirve como
        # prueba de identidad hasta que el dueño la cambia.
        "debe_cambiar_password": True,
        "creado_por": creado_por,
    }
    fila.update({c: bool(permisos.get(c)) for c in CLAVES_PERMISO})
    get_supabase().table(TABLA).insert(fila).execute()


def actualizar_permisos(usuario, permisos, es_admin=None):
    cambios = {c: bool(permisos.get(c)) for c in CLAVES_PERMISO}
    if es_admin is not None:
        cambios["es_admin"] = bool(es_admin)
    get_supabase().table(TABLA).update(cambios).eq("usuario", usuario).execute()


def actualizar_nombre(usuario, nombre):
    get_supabase().table(TABLA).update({"nombre": nombre.strip()}) \
        .eq("usuario", usuario).execute()


def set_activo(usuario, activo):
    get_supabase().table(TABLA).update({"activo": bool(activo)}) \
        .eq("usuario", usuario).execute()


def resetear_password(usuario, password_nueva):
    """El admin fija una contraseña provisoria; el dueño debe cambiarla al entrar."""
    get_supabase().table(TABLA).update({
        "password_hash": hash_password(password_nueva),
        "debe_cambiar_password": True,
    }).eq("usuario", usuario).execute()


def cambiar_password_propia(usuario, password_nueva):
    """El dueño fija su contraseña: acá sí se levanta la bandera."""
    get_supabase().table(TABLA).update({
        "password_hash": hash_password(password_nueva),
        "debe_cambiar_password": False,
    }).eq("usuario", usuario).execute()


def marcar_acceso(usuario):
    """Sella el último ingreso. Nunca frena el login si falla."""
    try:
        from datetime import datetime, timezone
        get_supabase().table(TABLA).update(
            {"ultimo_acceso": datetime.now(timezone.utc).isoformat()}
        ).eq("usuario", usuario).execute()
    except Exception:  # noqa: BLE001
        pass


def hay_admin_activo(df=None):
    """True si queda al menos un admin activo.

    Se chequea antes de quitarle el admin a alguien o desactivarlo: quedarse sin
    ningún administrador deja la administración de usuarios inaccesible desde la
    app y obliga a entrar a Supabase a mano.
    """
    d = leer_usuarios() if df is None else df
    if d.empty:
        return False
    return bool((d["es_admin"].fillna(False) & d["activo"].fillna(False)).any())


def otros_admins_activos(df, usuario):
    """Cantidad de admins activos que NO son `usuario`."""
    if df.empty:
        return 0
    otros = df[df["usuario"] != usuario]
    if otros.empty:
        return 0
    return int((otros["es_admin"].fillna(False) & otros["activo"].fillna(False)).sum())
