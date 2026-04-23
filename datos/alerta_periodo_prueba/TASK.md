# Alerta de Período de Prueba — Empleados Mes 5

## Descripción
Consulta la API de empleados de MasterBus, detecta los que están cumpliendo su 5° mes de período de prueba (entre 150 y 180 días desde el ingreso) y envía una alerta única por email a RRHH con una tabla resumen.

## Cuándo usar este script
- "Avisame qué empleados están por cumplir el período de prueba"
- "Alertar a RRHH sobre empleados en mes 5"
- "Revisar quiénes están cerca de terminar los 6 meses de prueba"
- "Ejecutar la alerta de período de prueba"

## Prerequisitos
- Variables de entorno requeridas en `.env` (raíz de automatizaciones):
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
  - `RRHH_EMAIL`
- Dependencias: `pip install -r requirements.txt`
- Acceso a Internet para consultar la API de MasterBus

## Cómo ejecutar

### Modo prueba (sin enviar email)
```bash
python main.py --dry-run
```

### Ejecución real (envía email a RRHH)
```bash
python main.py
```

### Ejecución automática diaria (cron)
```bash
0 8 * * * cd /ruta/a/automatizaciones/datos/alerta_periodo_prueba && /ruta/a/python main.py
```

### Todos los parámetros
| Parámetro  | Tipo | Requerido | Default | Descripción                              |
|------------|------|-----------|---------|------------------------------------------|
| `--dry-run`| flag | No        | False   | Muestra resultados sin enviar email      |

### Variables de entorno opcionales
| Variable           | Default | Descripción                                |
|--------------------|---------|--------------------------------------------|
| `MASTERBUS_API_URL`| URL de la API de MasterBus | URL de la API de empleados |
| `ALERTA_DIA_MIN`   | `150`   | Día mínimo para considerar "mes 5"         |
| `ALERTA_DIA_MAX`   | `180`   | Día máximo para considerar "mes 5"         |
| `SMTP_USE_TLS`     | `true`  | Usar TLS para la conexión SMTP             |

## Output esperado
- **Consola**: Tabla con empleados detectados (legajo, nombre, cargo, empleador, fecha ingreso, días)
- **Email**: Email HTML a RRHH con la misma información en formato profesional
- **Archivo**: `notificados.json` se actualiza con los empleados notificados
- **Log**: `automatizaciones/logs/alerta_periodo_prueba.log`

## Errores comunes y soluciones
| Error                           | Causa                              | Solución                                    |
|---------------------------------|------------------------------------|---------------------------------------------|
| `SMTP_HOST not found`           | Falta variable de entorno          | Configurar `SMTP_HOST` en `.env`            |
| `RRHH_EMAIL not found`          | Falta variable de entorno          | Configurar `RRHH_EMAIL` en `.env`           |
| `Error al consultar la API`     | Sin conexión o API caída           | Verificar acceso a Internet y URL de la API |
| `Error al enviar email`         | Credenciales SMTP incorrectas      | Verificar `SMTP_USER` y `SMTP_PASSWORD`     |
| Email no llega                  | Puerto o TLS mal configurado       | Verificar `SMTP_PORT` y `SMTP_USE_TLS`      |

## Notas
- El script **solo notifica una vez por empleado**. El archivo `notificados.json` lleva el registro. Para re-enviar una alerta, eliminar la entrada del empleado de ese archivo.
- Si se ejecuta con `--dry-run`, no se requieren las variables SMTP configuradas.
- Las fechas inválidas (`00/00/0000`) en los datos de la API se ignoran silenciosamente.
- Solo se evalúan empleados con `activo = "1"` y sin fecha de fin.
