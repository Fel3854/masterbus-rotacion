# Manual de Usuario: Plataforma de RRHH - Grupo Master

Este manual está diseñado para explicarte paso a paso cómo utilizar el **Dashboard de Rotación y Gestión de Novedades (Adelantos, Descuentos y Vencimientos)**. La herramienta está pensada para el uso intensivo (*heavy user*) del departamento de Recursos Humanos, centralizando la información en un solo lugar.

---

## 1. Acceso a la Plataforma

Para acceder a la plataforma, debes ingresar a la URL que se te ha proporcionado (por ejemplo, mediante el enlace de Streamlit Cloud o la URL interna). 
Al ingresar, verás un menú lateral (a la izquierda) que te permitirá navegar entre los distintos módulos:
1. **Dashboard** (Rotación de Personal)
2. **Adelantos de Sueldo**
3. **Descuentos**
4. **Vencimientos**

---

## 2. Flujo de Trabajo 1: Dashboard de Rotación

Esta sección te permite monitorear y analizar los ingresos y egresos de personal en todas las empresas del Grupo Master de forma automática.

### ¿Cómo funciona?
Los datos de este panel se sincronizan directamente con la base de datos de MasterBus. Se actualizan por defecto cada hora. Si necesitas forzar la actualización para ver un cambio muy reciente, puedes presionar el botón **"Actualizar datos"** en el menú izquierdo.

### Herramientas y Filtros
En el panel lateral izquierdo tienes varias opciones para filtrar la información que estás viendo:
- **Vista Mensual o Anual**: Te permite elegir si quieres ver los datos mes a mes, o el resumen consolidado de todo un año.
- **Selector de Período (Año y Mes)**: Elige el período específico que deseas analizar.
- **Filtro por Cargo / Puesto**: Puedes seleccionar uno o varios cargos (ej. Conductores, Administrativos) para ver la rotación específica de ese grupo. Si lo dejas vacío, se incluyen todos.
- **Filtro por Sector / Operación**: Filtra por la operación a la que pertenece el personal.

### Lectura de KPIs (Indicadores Principales)
Una vez aplicados los filtros, la pantalla central mostrará los indicadores clave del período seleccionado comparados con el período anterior:
- **Plantilla al inicio**: Cuántos empleados estaban activos el primer día del mes/año.
- **Bajas y Altas**: La cantidad exacta de ingresos y egresos.
- **Tasa de Rotación**: El porcentaje de bajas sobre la plantilla promedio. Si este número es superior a la media histórica del Grupo, verás una etiqueta roja indicando "**Elevada**" y un aviso de alerta.
- **Antigüedad media de bajas**: Te muestra cuántos meses en promedio llevaban en la empresa las personas que se fueron.

### Gráficos
En la parte inferior cuentas con pestañas para ver los gráficos de **Evolución Histórica** (te mostrará cómo se viene comportando la tasa en el tiempo y marcará con líneas punteadas el promedio y el límite de alerta) y el **Volumen de Altas y Bajas**.

---

## 3. Flujo de Trabajo 2: Adelantos de Sueldo y Descuentos

Los módulos de **Adelantos** y **Descuentos** funcionan de manera idéntica. Su objetivo es registrar novedades económicas del personal activo para luego exportarlas al sistema de liquidación de sueldos.

### Paso 1: Registro de la Novedad (Alta)
En la parte izquierda de la pantalla, verás el formulario de carga:
1. **Empleado**: Empieza a escribir el nombre, apellido o legajo y selecciona al empleado de la lista. *(Nota: solo aparecerán empleados activos).*
2. **Fecha**: Selecciona la fecha a la que corresponde la novedad (por defecto es hoy).
3. **Monto**: Ingresa el monto en pesos (sin puntos ni comas, por ejemplo `50000`).
4. **Motivo (Opcional)**: Agrega un detalle si lo necesitas para control interno.
5. Haz clic en **Registrar adelanto / descuento**. Verás un mensaje de éxito verde confirmando la operación.

### Paso 2: Control del Mes (Resumen)
A la derecha de la pantalla, tienes las estadísticas en tiempo real del mes en curso. Verás la cantidad de registros que has cargado en el mes y el monto total acumulado, así como el último registro que se hizo (muy útil para comprobar que no te faltó ninguno tras una carga masiva).

### Paso 3: Descarga para Liquidación
A fin de mes (o en el momento del corte), debes exportar estas novedades para el sistema contable/sueldos:
1. Desplázate hasta la sección **Descargar listado**.
2. Selecciona las fechas de corte en **"Desde"** y **"Hasta"** (por ejemplo, del 01 al 30 del mes).
3. Aparecerá en pantalla la tabla con todos los registros encontrados y los totales. Revisa que todo sea correcto.
4. Presiona el botón **⬇ Descargar TXT**. Esto te bajará un archivo con el formato exacto requerido por el sistema (número de legajo y monto formateado).

### Paso 4: Corrección de Errores (Eliminar)
Si cargaste un monto mal o te equivocaste de empleado:
1. Ve al final de la página a la pestaña desplegable **Eliminar un registro**.
2. Busca el registro erróneo en la lista desplegable (están ordenados por fecha e indican el nombre y el monto).
3. Presiona **Eliminar registro** y confirma la acción en el botón rojo **"Sí, eliminar"**. El registro se borrará de inmediato y el resumen se recalculará.

---

## 4. Flujo de Trabajo 3: Vencimientos

*(Nota: Este módulo gestiona las fechas límite)*

Esta pantalla te muestra listados de personal o recursos que tienen documentación o habilitaciones próximas a vencer. 
- Utiliza la tabla en pantalla para ordenar (haciendo clic en el encabezado de las columnas) y ver quiénes requieren atención inmediata (color rojo/amarillo según cercanía).
- Es una herramienta de control y consulta diaria para que RRHH pueda anticiparse y notificar a los empleados.

---

## Buenas Prácticas y Consejos para el Usuario Frecuente

1. **Búsqueda rápida en desplegables**: En los campos de selección de "Empleado", no busques con el mouse. Haz clic en la caja, escribe el nombre o número de legajo en tu teclado, y presiona `Enter`. Esto agiliza la carga enormemente.
2. **Descarga el TXT el día de cierre**: Generar el archivo TXT es automático, evita llevar controles paralelos en Excel. Todo lo que cargues aquí quedará guardado de manera segura en la base de datos en la nube.
3. **Limpiar filtros**: Si en el Dashboard los números te parecen raros, verifica siempre en el panel izquierdo que no tengas filtros activos por error. Usa el botón "Borrar filtros" para resetear la vista.
4. **Actualizar datos vs Cache**: El sistema guarda la información general de rotación durante 1 hora para que sea muy rápido al navegar. Si el sistema de personal dio de baja a alguien hace 5 minutos y no lo ves reflejado, usa el botón "Actualizar datos" del menú lateral.
