"""Lectura paginada de Supabase.

PostgREST (la API de Supabase) devuelve como mucho 1000 filas por consulta y NO
avisa cuando corta: un `.limit(5000)` también recibe 1000, sin error. Cualquier
lectura que pueda pasar ese número —un rango de fechas largo, una tabla que
crece— tiene que pedirse de a páginas, o la pantalla muestra un recorte como si
fuera el total y los totales y las exportaciones salen incompletos.

Módulo puro (sin Streamlit) para poder usarlo desde `postulantes.py` y testearlo
sin levantar la app. Las páginas lo importan desde `utils`.
"""

from __future__ import annotations

# Lo que se pide por página. Es el tope por defecto de Supabase; si el proyecto
# tuviera uno más bajo, el conteo exacto (ver abajo) igual lo resuelve.
PAGINA = 1000


def leer_paginado(armar_consulta, pagina=PAGINA, tope=None) -> list:
    """Todas las filas de una consulta, pidiéndolas de a páginas.

    `armar_consulta` es una función sin argumentos que devuelve la consulta ya
    filtrada y ordenada, sin `.execute()`. Se la llama una vez por página porque
    el constructor de consultas acumula parámetros y no se puede reutilizar.

    Dos cosas que la consulta TIENE que traer:

      · Un orden único. Si el orden admite empates (por ejemplo, sólo por
        fecha), Postgres puede devolver los empatados en distinto orden en cada
        página: una fila se repite y otra se pierde. Cerrar siempre con
        `.order("id")` o la clave que corresponda.
      · `count="exact"` en el `.select(...)`. Con el total a la vista se corta
        cuando están todas las filas, sin depender de cuántas entrega el
        servidor por página. Sin el conteo se corta en la primera página que
        viene incompleta, lo que sólo es correcto si el tope del servidor no es
        menor que `pagina`.

    `tope` limita cuántas filas se traen como máximo (None = todas). Para saber
    si quedó algo afuera, pedir una de más y comparar.
    """
    filas: list = []
    while tope is None or len(filas) < tope:
        pedir = pagina if tope is None else min(pagina, tope - len(filas))
        desde = len(filas)
        resp = armar_consulta().range(desde, desde + pedir - 1).execute()
        lote = resp.data or []
        filas.extend(lote)
        if not lote:
            break
        total = getattr(resp, "count", None)
        if total is not None:
            if len(filas) >= total:
                break
        elif len(lote) < pedir:
            break
    return filas
