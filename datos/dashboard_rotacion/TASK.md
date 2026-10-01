# Dashboard de Rotación de Personal — Grupo Master

## Descripción
Dashboard web interactivo que calcula y visualiza la tasa de rotación de empleados del Grupo Master. Permite consultar períodos mensuales y anuales desde 2020, filtrar por cargo y sector, y ver el detalle de cada baja.

## Cuándo usar este script
- "Ver la rotación del mes/año"
- "Cuántos empleados dejaron el grupo en 2023"
- "Rotación de conductores en Operación Campana"
- "Dashboard de RRHH"

## Prerequisitos
- Python 3.9+
- Dependencias: `pip install -r requirements.txt`
- Acceso a Internet para consultar la API de MasterBus (no requiere credenciales)

## Empresas del Grupo Master incluidas
| Empresa | Descripción |
|---|---|
| MASTER BUS S.A / MASTER BUS SA / MASTER BUS TASA | Empresa principal |
| SINTRA | |
| M B M S.A. | |
| MASTER MINING SA | |
| SOLUCIONES IOT S.A. | IT / tecnología de flota |
| ENDUROCO LATAM SA | |

## Fórmula de rotación
```
Tasa de Rotación (%) = Bajas del período / Plantilla al inicio del período × 100
```
- **Plantilla al inicio**: empleados activos el primer día del período (ingresaron antes y no se habían ido aún). Se excluyen los inactivos sin fecha de baja registrada (egresos no fechados en MasterBus), que de otro modo inflarían la dotación.
- **Bajas**: empleados cuya fecha de fin cae dentro del período
- **Bajas sin fecha registrada**: empleados marcados como inactivos pero sin `fechafin`. No se cuentan en la rotación porque no se pueden ubicar en un período; se listan aparte (con exportación CSV) para corregir la fecha en MasterBus.

## Cómo ejecutar localmente

```bash
cd automatizaciones/datos/dashboard_rotacion
pip install -r requirements.txt
python3 -m streamlit run app.py
```

> Usar `python3 -m streamlit`: el shebang del venv apunta a una ruta vieja y el comando `streamlit` directo falla.

Se abre en el navegador en `http://localhost:8501`

## Cómo deployar en Streamlit Community Cloud (gratis)

1. Subir el repo a GitHub (si no está ya)
2. Ir a [share.streamlit.io](https://share.streamlit.io) e iniciar sesión con GitHub
3. Click en **New app**
4. Seleccionar el repo, branch `main`
5. **Main file path**: `automatizaciones/datos/dashboard_rotacion/app.py`
6. Click **Deploy** — listo, queda en una URL pública

> Streamlit Cloud detecta automáticamente el `requirements.txt` en la misma carpeta.

## Funcionalidades del dashboard

| Función | Descripción |
|---|---|
| Vista Mensual / Anual | Cambia la granularidad del período |
| Selector de año/mes | Períodos desde enero 2020 hasta el mes actual |
| Filtro por Cargo | Multiselect — vacío = todos |
| Filtro por Sector | Multiselect — vacío = todos |
| KPIs | Plantilla, Bajas, Altas, Tasa de Rotación |
| Gráfico de línea | Evolución histórica de la tasa |
| Gráfico de barras | Altas vs Bajas en el tiempo |
| Desglose por Cargo | Bajas del período por puesto |
| Desglose por Sector | Bajas del período por operación |
| Tabla de detalle | Listado individual de cada baja con exportación CSV |
| Actualizar datos | Botón para forzar recarga de la API (cache de 1 hora) |

## Otros módulos de la plataforma

| Módulo | Descripción |
|---|---|
| Adelantos de Sueldo | Alta de adelantos + exportación Excel formato Santander |
| Descuentos | Alta de descuentos con cuotas + exportación TXT para liquidación |
| Vencimientos | Control de documentación y habilitaciones próximas a vencer |
| **Seguimiento** | **Entrevista de seguimiento del 2° mes de cada conductor: carga tabulada, cola de pendientes e indicadores de adaptación** |
| Minutas Reunión | Temas y acciones de RRHH con estado y fecha límite |
| Postulantes | Consulta del registro de entrevistas a postulantes (FORM 045 02), alimentado desde Access. Sólo con permiso `ver_postulantes` |
| Auditoría | Registro de movimientos de los usuarios (`auditoria.py`). Sólo admin; tabla append-only |
| Usuarios | Alta, permisos y contraseñas (`usuarios.py`). Sólo admin |
| Manual de Usuario | Renderiza `automatizaciones/docs/manual_usuario.md` |

### Usuarios y autenticación

`usuarios.py` + `pages/8_Usuarios.py` + `migration_usuarios.sql`.

Los usuarios dejaron de ser el dict `USERS` de `auth.py` y viven en la tabla
`usuarios`: un admin no puede editar el código desde la app, así que para dar de
alta a alguien sin tocar el repo tienen que ser datos. `auth.current_user()` lee
esa tabla con una caché de 30 s (TTL corto a propósito: quitarle un permiso a
alguien tiene que surtir efecto rápido).

Contraseñas hasheadas con PBKDF2-HMAC-SHA256, salt por usuario, 400k
iteraciones, formato `pbkdf2_sha256$iter$salt$hash`. Stdlib a propósito: sumar
bcrypt/argon2 metería una dependencia compilada al deploy para proteger siete
cuentas internas. `usuarios.COLUMNAS` **excluye** `password_hash`; sólo se pide
al validar un login.

Invariantes con test:
- `es_admin` no arrastra permisos de edición (administrar ≠ operar).
- La pantalla no deja quitar ni desactivar al último admin activo
  (`otros_admins_activos`): sin admin, la administración queda inaccesible.
- Los usuarios se desactivan, no se borran: la auditoría los referencia.

Ojo: `_signing_key()` ya NO deriva de `st.secrets["passwords"]` (esa sección
quedó obsoleta). Usa `AUTH_SECRET` o, en su defecto, `SUPABASE_KEY`, y **falla
fuerte** si no hay ninguno: con la llave vacía cualquiera se firmaría una cookie
de admin.

### Auditoría

`auditoria.py` + `pages/7_Auditoria.py` + `migration_auditoria.sql`.

`auditoria.registrar(modulo, accion, detalle, registro_id, datos)` se llama
DESPUÉS de cada escritura y nunca lanza excepción: si el log falla, la acción
del usuario ya se hizo. Puntos instrumentados: altas/bajas/cambios de los cuatro
módulos, la administración de usuarios, exportaciones sensibles (Santander con CUIL/CBU, entrevistas con
textuales), apertura de una entrevista con permiso de textuales, y login /
logout / login fallido.

Dos invariantes que tienen test:
- El log **no** guarda respuestas de entrevistas, sólo que alguien las abrió.
- La tabla es **append-only**: las policies son `FOR INSERT` y `FOR SELECT`, no
  hay `FOR ALL`. Corregir el historial exige la service key desde Supabase.

Ojo con el volumen: la apertura de la vista ampliada se audita al SETEAR
`ver_id_sg`, no al renderizar — la vista se repinta en cada rerun.

### Postulantes

`postulantes.py` + `pages/9_Postulantes.py` + `migration_entrevistas_postulantes.sql` + `tests/test_postulantes.py`.

Consulta del registro de entrevistas a postulantes (FORM 045 02). **Access sigue
siendo donde se carga**; la tabla `entrevistas_postulantes` es su copia y se pone
al día subiendo el archivo desde la pestaña «Actualizar desde Access» (upsert por
`numero_orden`, el autonumérico de Access).

- **Se guarda crudo, se deriva al leer.** La tabla tiene el dato tal cual viene,
  con sus typos. Familia de puesto (161 variantes → 9 familias), sector
  normalizado, entrevistador unificado y «veces que se presentó» se calculan en
  `enriquecer()` y no se guardan.
- **`apto` sólo significa algo en TRUE.** Desde 2023 la casilla casi no se tilda
  (2 % en 2025, con «OK PREOCU» en las notas). FALSE es "sin marcar", no
  "rechazado": la pantalla nunca muestra «No apto» ni calcula tasas de rechazo, y
  hay un test que lo protege.
- **El DNI 0 o vacío nunca agrupa.** 263 entrevistas no tienen DNI; si el 0
  agrupara serían una sola "persona". El historial es estrictamente por DNI válido.
- **Permiso `ver_postulantes`**: es de LECTURA (la pestaña no aparece sin él) y
  además habilita actualizar. No lo arrastra `es_admin`. Es la única sección de
  datos que no ven todos, porque las notas tienen datos delicados.
- **RLS sin DELETE**: policies de SELECT, INSERT y UPDATE; ni DELETE ni FOR ALL.
  La app suma y corrige, nunca borra. Con test sobre el DDL.
- **Lectura paginada**: `leer_todo()` usa `paginado.leer_paginado` (ver «Lecturas
  a Supabase» más abajo).
- **Lectura del `.mdb`**: `access-parser` (Python puro) con dos correcciones
  aplicadas al objeto de la tabla en `_leer_mdb()`: una fecha con bytes inválidos
  es un vacío, y cada columna de texto se lee de su `variable_column_number`. Sin
  la segunda, como a la tabla se le borró una columna, los textos salen corridos
  un lugar y se pierden las observaciones. La versión está **fijada** en
  `requirements.txt`. Para revalidar tras cambiarla:
  `POSTULANTES_MDB=… POSTULANTES_CSV=… python3 -m pytest tests/test_postulantes.py -k mdb`
  (compara el `.mdb` real contra su export de referencia; tiene que dar 0 diferencias).
- **Dos frenos antes de confirmar una carga** (`advertencias_de_carga`): al
  archivo le faltan entrevistas que ya están (copia vieja), o cambia más del 20 %
  de lo cargado (archivo mal leído). En ambos casos hay que tildar una confirmación.
- **Auditoría**: se registran exportaciones (cantidad y filtros) y actualizaciones
  (cantidades y nombre de archivo). Nunca el contenido de las notas.
- **Datos reales fuera del repo**: los tests usan nombres y DNI inventados. El
  `.mdb` y sus exports no se versionan.

### Lecturas a Supabase: siempre paginadas

`paginado.py` + `tests/test_paginado.py`. Las páginas lo importan desde `utils`.

PostgREST devuelve como mucho **1000 filas por consulta y no avisa cuando
corta** (verificado: un `.limit(5000)` recibía 1000). Toda lectura que pueda
pasar ese número va por `leer_paginado(armar_consulta)`: Adelantos, Descuentos,
Seguimiento, Minutas, Auditoría y Postulantes. Dos reglas para cada consulta:

- **Orden único**: cerrar con `.order("id")` (o la clave). Con empates, Postgres
  puede ordenar distinto en cada página y una fila se repite mientras otra se
  pierde. Adelantos y Descuentos desempatan por `fecha_registro` y después `id`.
- **`count="exact"` en el `.select()`**: con el total a la vista se corta cuando
  están todas, sin depender del tope del servidor.

Auditoría además tiene un máximo de 5000 movimientos en pantalla (dibuja un
renglón por cada uno): pide uno de más y, si el período no entra, **avisa** en
vez de recortar en silencio.

### Seguimiento de Conductores

Digitaliza el formulario de entrevista del 2° mes (`seguimiento_Conductor_2do_Mes.xlsx`).

- **Tabulación**: cada una de las 18 preguntas abiertas tiene una respuesta cerrada codificada además del textual. 11 escalas 1-4, 2 flags Sí/No y 5 categorías. El catálogo `PREGUNTAS` en `seguimiento.py` es la única fuente de verdad: maneja el render del formulario, el insert y las métricas.
- **Escala**: Mala=1 · Regular=2 · Buena=3 · Muy buena=4 (la misma que traía la validación del xlsx). Los índices se normalizan a 0-100 con `(promedio − 1) / 3 × 100`; **67 equivale a responder "Buena" en todo** — con escala de 4 puntos no hay punto medio, así que 50 no es neutro.
- **Dimensiones ≠ secciones**: las secciones 1-6 ordenan el formulario; las dimensiones agrupan para los índices. La pregunta 6 se muestra en la sección 2 pero indexa en *Vínculos* (mide lo mismo que la 14). Las preguntas 8 y 20 no forman índice: un promedio de un solo ítem es la pregunta con decimales.
- **Permisos**: `edit_seguimiento` en `auth.py` (hoy Lu y Flor). Además de habilitar la carga, **gatea la lectura de las respuestas textuales**, que son confidenciales.
- **Tabla**: `seguimiento_conductores` (47 columnas). Ver `migration_seguimiento_conductores.sql`. Clave única `(legajo, empleador, fecha_entrevista)`: bloquea el duplicado por doble submit pero permite un re-seguimiento posterior. El legajo no es único entre empresas.
- **Índices no se guardan**: se recalculan en pandas para que la fórmula viva en un solo lugar.
- **Tests**: `python3 -m pytest tests/ -q` (40 tests, sin Streamlit ni red).

## Parámetros / Variables de entorno
La URL de la API está embebida en el código (`API_URL` en `utils.py` y `_dashboard.py`).
Los módulos que escriben en base (Adelantos, Descuentos, Seguimiento) necesitan
`SUPABASE_URL` y `SUPABASE_KEY` en `.streamlit/secrets.toml`, junto con la tabla
`[passwords]` del login.

## Notas
- Los datos se cachean 1 hora para no saturar la API.
- Solo se consideran empleados cuya empresa pertenece al Grupo Master.
- Las fechas inválidas (`00/00/0000`, null) se ignoran.
