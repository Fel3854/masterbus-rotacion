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
| Manual de Usuario | Renderiza `automatizaciones/docs/manual_usuario.md` |

### Seguimiento de Conductores

Digitaliza el formulario de entrevista del 2° mes (`seguimiento_Conductor_2do_Mes.xlsx`).

- **Tabulación**: cada una de las 20 preguntas abiertas tiene una respuesta cerrada codificada además del textual. 13 escalas 1-4, 2 flags Sí/No y 5 categorías. El catálogo `PREGUNTAS` en `seguimiento.py` es la única fuente de verdad: maneja el render del formulario, el insert y las métricas.
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
