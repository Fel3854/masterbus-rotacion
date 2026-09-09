# Manual de Usuario: Plataforma de RRHH - Grupo Master

Este manual está diseñado para explicarte paso a paso cómo utilizar el **Dashboard de Rotación y Gestión de Novedades (Adelantos, Descuentos, Vencimientos y Seguimiento de Conductores)**. La herramienta está pensada para el uso intensivo (*heavy user*) del departamento de Recursos Humanos, centralizando la información en un solo lugar.

---

## 1. Acceso a la Plataforma

Para acceder a la plataforma, debes ingresar a la URL que se te ha proporcionado (por ejemplo, mediante el enlace de Streamlit Cloud o la URL interna). 
Al ingresar, verás un menú lateral (a la izquierda) que te permitirá navegar entre los distintos módulos:
1. **Dashboard** (Rotación de Personal)
2. **Adelantos de Sueldo**
3. **Descuentos**
4. **Vencimientos**
5. **Seguimiento** (entrevistas de conductores)
6. **Minutas Reunión** (temas y acciones de RRHH)
7. **Auditoría** y **Usuarios** (sólo visibles para el administrador)

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

## 5. Flujo de Trabajo 4: Seguimiento de Conductores

Este módulo digitaliza la **entrevista de seguimiento del 2° mes**: la charla individual que RRHH tiene con cada conductor nuevo a los dos meses de haber ingresado. El objetivo no es evaluarlo, sino detectar a tiempo problemas de adaptación, de seguridad o de clima, antes de que se transformen en una baja.

**Quién puede cargar entrevistas:** los usuarios con el permiso de *Seguimiento* activado (se administra desde la pestaña Usuarios). El resto —incluidas las gerencias— ve los indicadores, los puntajes y la cola de pendientes, pero **no** las respuestas textuales: el conductor las da bajo promesa de confidencialidad, así que las citas quedan reservadas a quien realiza la entrevista.

La pantalla tiene tres pestañas.

### Pestaña 1: Nueva entrevista

A la izquierda está el formulario; a la derecha, **la cola de pendientes**.

1. **Conductor**: escribí nombre, apellido o legajo. Solo aparecen conductores activos.
2. **Fecha de la entrevista** y **Entrevistador** (se completa solo con tu usuario).
3. **Las 18 preguntas**, agrupadas en las 6 secciones del formulario en papel. Cada una tiene:
   - Una **respuesta cerrada** (los botones tipo píldora): es la que se mide. Ninguna viene preseleccionada a propósito, para que no queden respuestas puestas por descuido.
   - En algunas, un campo de **textual** para registrar lo que dijo el conductor con sus palabras.
4. **Sección 7 – Autopercepción**: el conductor se evalúa a sí mismo en las 4 áreas (Operaciones, Seguridad Vial, RRHH y Mantenimiento).
5. **Sección 8 – Conclusión**: fortalezas, aspectos a mejorar, compromisos y fecha del próximo seguimiento.

**Importante**: las 20 respuestas cerradas y las 4 de autopercepción son obligatorias — son las que permiten medir. Los textuales son opcionales, salvo en las preguntas 9 y 16: si ahí respondiste "Sí", tenés que detallar cuál es el problema.

Si te falta alguna respuesta, el sistema te avisa **todas juntas** en un solo mensaje y **no se pierde nada de lo que ya cargaste**. Podés completar lo que falta y volver a enviar.

**Cola de pendientes**: lista los conductores activos que ya tienen entre 45 y 120 días de antigüedad y todavía no tienen entrevista cargada. Los que pasaron los 90 días figuran como *Vencidos*. Es la lista de trabajo del mes.

### Pestaña 2: Entrevistas cargadas

Primero se muestran las **alertas**, porque son lo más importante de esta pantalla. Una entrevista queda marcada cuando:

- El conductor dice que hay una **norma de seguridad difícil de cumplir** (pregunta 9).
- El conductor dice que hay una **situación del ambiente laboral que lo incomoda** (pregunta 16).
- **No recomendaría** la empresa (pregunta 20).
- **No recibió** capacitación de Seguridad Vial (pregunta 8).
- Su **índice general es menor a 50**, o respondió Regular/Mala en 3 o más preguntas.

Debajo está la tabla de entrevistas del período, con filtros por fecha, base y empleador, y el botón para **descargar todo a Excel**. Si no tenés permiso de carga, el Excel sale sin las columnas de textuales.

Al final, quien tiene permiso puede **eliminar** una entrevista cargada por error (pide confirmación).

### Pestaña 3: Indicadores

Todo lo de esta pestaña es agregado: **no aparecen nombres**.

**Cómo leer los índices**: todas las respuestas cerradas usan la misma escala de 4 puntos (Mala=1, Regular=2, Buena=3, Muy buena=4), que después se lleva a una escala de 0 a 100 para que sea más fácil de comparar.

> **El número de referencia es 67.** Equivale a que todos hayan respondido "Buena" en todo. Por debajo de 50 la situación es crítica; por encima de 84, muy buena. **50 no es "neutro"**: con una escala de 4 puntos no hay punto medio.

- **Las 6 tarjetas de arriba**: entrevistas cargadas, cobertura, índice general, autopercepción, cuántos recomendarían la empresa y cuántas entrevistas tienen alerta.
- **Índice por dimensión**: agrupa las preguntas en Adaptación, Operación, Condiciones y Vínculos. Cada barra aclara con cuántas preguntas se calcula. Las dos últimas filas son preguntas sueltas, no índices.
- **Respuestas por pregunta**: la pregunta con peor promedio queda arriba. Es el gráfico más accionable: te dice exactamente dónde está el problema.
- **Qué dicen los conductores**: frecuencia de las respuestas de categoría. "Lo que menos gusta" y "qué cambiarías" miden lo mismo desde ángulos distintos — lo interesante es dónde no coinciden.
- **Índice por base**: solo se muestran bases con 5 o más entrevistas, para no sacar conclusiones de un caso suelto.
- **Cobertura por mes de ingreso**: de los que entraron cada mes, a cuántos se entrevistó. El denominador **incluye a quienes ya se dieron de baja**: si no, un conductor que renunció sin ser entrevistado inflaría la cobertura justo en el caso que más importa.

---

## 6. Auditoría: quién hizo qué

Todo movimiento que cambia datos queda registrado. La pestaña **Auditoría** muestra ese registro y sólo la ve el **administrador**.

### Qué se registra
| Acción | Cuándo se anota |
|---|---|
| **Alta** | Se carga un adelanto, un descuento, una entrevista o una minuta |
| **Baja** | Se elimina cualquiera de esos registros |
| **Cambio** | Se edita una minuta o se cambia su estado |
| **Exportación** | Se descarga el Excel del Santander (lleva CUIL y CBU) o entrevistas de Seguimiento |
| **Usuarios** | Se crea un usuario, se le cambian los permisos, se le resetea la contraseña o se lo desactiva |
| **Lectura sensible** | Alguien abre una entrevista y ve las respuestas textuales del conductor |
| **Ingreso / Salida** | Login, logout e intentos de login fallidos |

De cada movimiento queda: fecha y hora, usuario, módulo, acción y un detalle legible (por ejemplo *"MARTINEZ JUAN (leg. 4821) · 15/09/2026 · $ 50.000"*).

**Lo que NO se registra:** el contenido de las respuestas de las entrevistas. Queda anotado que alguien la abrió, nunca lo que el conductor dijo. Si el textual se copiara al registro, el permiso que lo protege no serviría de nada.

### Cómo usarla
- **Movimientos**: la lista cronológica, agrupada por día. Se puede filtrar por usuario, por módulo, buscar texto en el detalle, o tildar *"Solo movimientos que cambiaron datos"* para sacar del medio los ingresos y salidas.
- **Por usuario**: cuántos movimientos hizo cada uno, cuántos de ellos modificaron datos y cuándo fue el último.
- El botón de descarga arma un Excel con lo que estés viendo filtrado.

### El registro no se puede borrar desde la app
La tabla acepta que se agreguen movimientos y que se lean, pero **no** que se editen ni se eliminen — ni siquiera por el administrador. Un registro de control que el propio auditado puede borrar no controla nada. Para corregir o purgar el historial hay que entrar al panel de Supabase con la clave de administrador.

---

## 7. Usuarios: altas, permisos y contraseñas

La pestaña **Usuarios** es del administrador. Desde ahí se da de alta a alguien nuevo, se le cambian los permisos o se le resetea la contraseña, sin tocar el código ni pedirle nada a nadie.

### Cómo funcionan los permisos
Hay una regla general y dos excepciones:

- **Todos ven todas las secciones.** Los permisos sólo habilitan *cargar, editar y eliminar*.
- **Excepción 1:** el permiso de *Seguimiento* además habilita ver las respuestas textuales de las entrevistas, que son confidenciales. Dárselo a alguien es dejarlo leer lo que el conductor dijo bajo promesa de confidencialidad.
- **Excepción 2:** *Administrador* es el único permiso de lectura. Habilita Auditoría y Usuarios, y **no** habilita cargar datos: administrar y operar se mantienen separados a propósito.

### Dar de alta a alguien
1. Pestaña **Nuevo usuario**.
2. **Usuario**: con lo que va a entrar (minúsculas, sin espacios). **Nombre visible**: el que aparece en la sesión y en la auditoría.
3. **Contraseña provisoria**: se la pasás por otro medio (WhatsApp, en persona). No la vas a poder ver de nuevo.
4. Tildás los permisos que necesita y **Crear usuario**.

En su primer ingreso, la app le va a exigir que cambie esa contraseña por una que **sólo él conozca**, y no lo deja entrar a nada hasta que lo haga. Lo mismo pasa cada vez que le reseteás la clave.

### Contraseñas
Se guardan **hasheadas**: ni el administrador puede ver la contraseña de otro. Si alguien se la olvida, no se recupera — se resetea desde el botón *Resetear contraseña* y la persona elige una nueva al entrar.

### Bajas
Un usuario **no se borra, se desactiva**. Deja de poder entrar, pero su historial en la auditoría sigue siendo legible: si se borrara la ficha, los movimientos viejos quedarían firmados por un fantasma. Se puede reactivar cuando haga falta.

La app tampoco te deja **quitarte el admin a vos mismo ni desactivar al último administrador activo**: si no queda ninguno, la administración de usuarios se vuelve inaccesible desde la app y hay que entrar a Supabase a mano.

---

## Buenas Prácticas y Consejos para el Usuario Frecuente

1. **Búsqueda rápida en desplegables**: En los campos de selección de "Empleado", no busques con el mouse. Haz clic en la caja, escribe el nombre o número de legajo en tu teclado, y presiona `Enter`. Esto agiliza la carga enormemente.
2. **Descarga el TXT el día de cierre**: Generar el archivo TXT es automático, evita llevar controles paralelos en Excel. Todo lo que cargues aquí quedará guardado de manera segura en la base de datos en la nube.
3. **Limpiar filtros**: Si en el Dashboard los números te parecen raros, verifica siempre en el panel izquierdo que no tengas filtros activos por error. Usa el botón "Borrar filtros" para resetear la vista.
4. **Actualizar datos vs Cache**: El sistema guarda la información general de rotación durante 1 hora para que sea muy rápido al navegar. Si el sistema de personal dio de baja a alguien hace 5 minutos y no lo ves reflejado, usa el botón "Actualizar datos" del menú lateral.
