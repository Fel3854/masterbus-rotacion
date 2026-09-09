"""Tests de usuarios.py — hash, validaciones y reglas de admin. Sin red."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import usuarios as us  # noqa: E402


# ─── Hash de contraseñas ──────────────────────────────────────
def test_el_hash_no_contiene_la_contrasena():
    h = us.hash_password("mi-clave-secreta")
    assert "mi-clave-secreta" not in h


def test_verifica_la_correcta_y_rechaza_la_incorrecta():
    h = us.hash_password("abcdefgh")
    assert us.verificar_password("abcdefgh", h)
    assert not us.verificar_password("abcdefgi", h)
    assert not us.verificar_password("", h)


def test_la_misma_clave_da_hashes_distintos():
    """Salt por usuario: dos personas con la misma clave no se delatan entre sí."""
    assert us.hash_password("abcdefgh") != us.hash_password("abcdefgh")


def test_un_hash_corrupto_no_revienta_devuelve_false():
    for basura in (None, "", "no-es-un-hash", "a$b$c$d", 12345,
                   "md5$1$c2FsdA==$aGFzaA==", "pbkdf2_sha256$x$y$z"):
        assert us.verificar_password("abcdefgh", basura) is False


def test_el_hash_lleva_sus_propias_iteraciones():
    """Si mañana sube el costo, las claves viejas se siguen verificando."""
    h = us.hash_password("abcdefgh")
    algoritmo, iteraciones, _salt, _hash = h.split("$")
    assert algoritmo == us.ALGORITMO
    assert int(iteraciones) == us.ITERACIONES


# ─── Validaciones ─────────────────────────────────────────────
def test_usuario_valido():
    for u in ("lu", "jperez", "maxi_2", "juan.cigna"):
        assert us.validar_usuario(u)[0], u


def test_usuario_invalido():
    for u in ("", "u", "Juan Perez", "juan perez", "juan@empresa", "u" * 21):
        assert not us.validar_usuario(u)[0], u


def test_las_mayusculas_se_normalizan_en_vez_de_rechazarse():
    """`crear()` guarda en minúsculas, así que tipear JPEREZ no es un error."""
    assert us.validar_usuario("JPEREZ")[0]


def test_usuario_invalido_explica_por_que():
    ok, error = us.validar_usuario("Juan Perez")
    assert not ok and error


def test_password_corta_se_rechaza():
    assert not us.validar_password("a" * (us.LARGO_MINIMO_PASSWORD - 1))[0]
    assert us.validar_password("a" * us.LARGO_MINIMO_PASSWORD)[0]


def test_password_con_espacios_en_los_bordes_se_rechaza():
    # Se copian y pegan sin querer y después nadie entiende por qué no entra.
    assert not us.validar_password(" abcdefgh")[0]
    assert not us.validar_password("abcdefgh ")[0]
    assert us.validar_password("abcd efgh")[0]


def test_las_dos_passwords_tienen_que_coincidir():
    assert not us.validar_password("abcdefgh", "abcdefgi")[0]
    assert us.validar_password("abcdefgh", "abcdefgh")[0]


# ─── Permisos ─────────────────────────────────────────────────
def test_resumen_de_permisos():
    assert us.resumen_permisos({"es_admin": True}) == "Administrador"
    assert us.resumen_permisos({}) == "Solo lectura"
    assert "Minutas" in us.resumen_permisos({"edit_minutas": True})


def test_el_admin_no_arrastra_permisos_de_edicion():
    """Administrar y operar van separados: es_admin no habilita cargar datos."""
    assert us.resumen_permisos({"es_admin": True, "edit_adelantos": False}) == "Administrador"


def test_las_claves_de_permiso_salen_del_catalogo():
    assert us.CLAVES_PERMISO == [c for c, _l, _d in us.PERMISOS]
    for clave, label, desc in us.PERMISOS:
        assert clave.startswith("edit_") and label and desc


# ─── Reglas de administrador ──────────────────────────────────
def _tabla(*filas):
    return pd.DataFrame(list(filas), columns=us.COLUMNAS)


def _u(usuario, es_admin=False, activo=True):
    fila = {c: False for c in us.COLUMNAS}
    fila.update({"usuario": usuario, "nombre": usuario.title(),
                 "activo": activo, "es_admin": es_admin})
    return fila


def test_hay_admin_activo():
    assert us.hay_admin_activo(_tabla(_u("felipe", es_admin=True), _u("lu")))
    assert not us.hay_admin_activo(_tabla(_u("lu"), _u("flor")))


def test_un_admin_desactivado_no_cuenta():
    assert not us.hay_admin_activo(_tabla(_u("felipe", es_admin=True, activo=False)))


def test_tabla_vacia_no_tiene_admin():
    assert not us.hay_admin_activo(_tabla())


def test_otros_admins_activos_protege_al_ultimo():
    """La pantalla usa esto para no dejar la app sin ningún administrador."""
    df = _tabla(_u("felipe", es_admin=True), _u("lu"))
    assert us.otros_admins_activos(df, "felipe") == 0     # es el único: no se toca
    df2 = _tabla(_u("felipe", es_admin=True), _u("lu", es_admin=True))
    assert us.otros_admins_activos(df2, "felipe") == 1     # hay otro: se puede


def test_otros_admins_ignora_a_los_desactivados():
    df = _tabla(_u("felipe", es_admin=True),
                _u("ex", es_admin=True, activo=False))
    assert us.otros_admins_activos(df, "felipe") == 0


def test_otros_admins_con_tabla_vacia():
    assert us.otros_admins_activos(_tabla(), "felipe") == 0


# ─── Esquema ──────────────────────────────────────────────────
def test_columnas_coinciden_con_el_ddl_menos_el_hash():
    """password_hash está en la tabla pero NO en las lecturas normales."""
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "migration_usuarios.sql")
    with open(ruta, encoding="utf-8") as fh:
        sql = fh.read()
    cuerpo = sql.split("CREATE TABLE IF NOT EXISTS usuarios (", 1)[1].split("\n);", 1)[0]
    cols = []
    for linea in cuerpo.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith(("--", "CONSTRAINT", "UNIQUE")):
            continue
        cols.append(linea.split()[0])
    assert "password_hash" in cols
    assert "password_hash" not in us.COLUMNAS
    assert sorted(cols) == sorted(us.COLUMNAS + ["password_hash"])
