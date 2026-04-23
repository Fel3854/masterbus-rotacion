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
- **Plantilla al inicio**: empleados activos el primer día del período (ingresaron antes y no se habían ido aún)
- **Bajas**: empleados cuya fecha de fin cae dentro del período

## Cómo ejecutar localmente

```bash
cd automatizaciones/datos/dashboard_rotacion
pip install -r requirements.txt
streamlit run app.py
```

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

## Parámetros / Variables de entorno
No requiere variables de entorno. La URL de la API está embebida en el código.
Para cambiarla, editar `API_URL` en `app.py`.

## Notas
- Los datos se cachean 1 hora para no saturar la API.
- Solo se consideran empleados cuya empresa pertenece al Grupo Master.
- Las fechas inválidas (`00/00/0000`, null) se ignoran.
