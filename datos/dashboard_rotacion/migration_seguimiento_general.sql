-- Migración: tabla seguimiento_general
-- Ejecutar una sola vez en el dashboard de Supabase → SQL Editor
--
-- Una fila = una «Encuesta de seguimiento – personal ingresante» (la de
-- efectivización) de alguien que NO es conductor. Los conductores tienen su
-- propia tabla, seguimiento_conductores, con otro cuestionario.
--
-- Es aditiva: sólo crea una tabla nueva y no toca ninguna de las que existen.
-- Se puede aplicar antes o después de publicar el código: hasta que esté, el
-- cuestionario de conductores sigue andando igual y el del resto del personal
-- avisa que no pudo cargar las entrevistas.
--
-- Escalas: se guarda la posición de la respuesta, de mejor a peor
--     3 opciones → 3 = la mejor (Sí / Muy buena / Muy conforme) · 1 = la más baja
--     4 opciones → 4 = Muy bueno · 1 = Insuficiente
-- Los puntos y los índices NO se guardan: se calculan en pandas
-- (seguimiento_general.py) para que la fórmula viva en un solo lugar.

CREATE TABLE IF NOT EXISTS seguimiento_general (
    -- ── Identificación (snapshot del padrón al momento de la entrevista) ──
    -- base / cargo / fecha_ingreso se desnormalizan a propósito, igual que en
    -- conductores: un cambio de puesto posterior no debe reescribir la
    -- entrevista. `sector` lo carga el entrevistador: el padrón no lo trae.
    id                 UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    legajo             TEXT NOT NULL,
    apenom             TEXT NOT NULL,
    empleador          TEXT NOT NULL,
    base               TEXT,          -- columna 'str' de MasterBus (operación)
    cargo              TEXT,          -- puesto según el padrón
    sector             TEXT NOT NULL,
    fecha_ingreso      DATE,
    fecha_entrevista   DATE NOT NULL,
    entrevistador      TEXT NOT NULL,
    registrado_por     TEXT,          -- usuario del dashboard que cargó la entrevista
    fecha_registro     TIMESTAMPTZ DEFAULT now(),

    -- ── Secciones 1-7: respuestas cerradas ──
    -- Escalas de 3 opciones (13 ítems, alimentan los índices)
    g01  SMALLINT CHECK (g01 BETWEEN 1 AND 3),
    g02  SMALLINT CHECK (g02 BETWEEN 1 AND 3),
    g03  SMALLINT CHECK (g03 BETWEEN 1 AND 3),
    g04  SMALLINT CHECK (g04 BETWEEN 1 AND 3),
    g06  SMALLINT CHECK (g06 BETWEEN 1 AND 3),
    g07  SMALLINT CHECK (g07 BETWEEN 1 AND 3),
    g08  SMALLINT CHECK (g08 BETWEEN 1 AND 3),
    g09  SMALLINT CHECK (g09 BETWEEN 1 AND 3),
    g11  SMALLINT CHECK (g11 BETWEEN 1 AND 3),
    g12  SMALLINT CHECK (g12 BETWEEN 1 AND 3),
    g13  SMALLINT CHECK (g13 BETWEEN 1 AND 3),
    g15  SMALLINT CHECK (g15 BETWEEN 1 AND 3),
    g16  SMALLINT CHECK (g16 BETWEEN 1 AND 3),

    -- Categorías cerradas que no puntúan (se guarda la etiqueta elegida)
    g05  TEXT,                       -- 'Sí' | 'Parcialmente' | 'No'
    g14  TEXT,                       -- 'Sí' | 'Tal vez' | 'No'

    -- ── Sección 8: evaluación general del sector (4 opciones) ──
    ev_desempeno   SMALLINT CHECK (ev_desempeno  BETWEEN 1 AND 4),
    ev_compromiso  SMALLINT CHECK (ev_compromiso BETWEEN 1 AND 4),
    ev_adaptacion  SMALLINT CHECK (ev_adaptacion BETWEEN 1 AND 4),

    -- ── Sección 9: resultado de la entrevista (lista fija en RESULTADOS) ──
    resultado  TEXT,

    -- ── Texto libre (confidencial: sólo lo ve quien tiene permiso de carga) ──
    g10               TEXT,   -- pregunta abierta: qué otra capacitación le sería útil
    g05_texto         TEXT,   -- obligatorio a nivel app cuando g05 = 'Sí'
    g14_texto         TEXT,   -- obligatorio a nivel app cuando g14 = 'Sí'
    obs_induccion     TEXT,   -- observaciones: una por sección, como en el papel
    obs_adaptacion    TEXT,
    obs_puesto        TEXT,
    obs_capacitacion  TEXT,
    obs_equipo        TEXT,
    obs_motivacion    TEXT,
    obs_expectativas  TEXT,
    obs_evaluacion    TEXT,
    observaciones_finales  TEXT,

    -- Evita el duplicado por doble submit sin bloquear una segunda entrevista
    -- de la misma persona en otra fecha. El legajo NO es único entre empresas,
    -- por eso la clave incluye el empleador.
    CONSTRAINT uq_seguimiento_general_legajo_empleador_fecha
        UNIQUE (legajo, empleador, fecha_entrevista)
);

CREATE INDEX IF NOT EXISTS idx_seguimiento_general_legajo
    ON seguimiento_general (legajo);
CREATE INDEX IF NOT EXISTS idx_seguimiento_general_fecha_entrevista
    ON seguimiento_general (fecha_entrevista DESC);

-- RLS: como en el resto del dashboard, la anon key opera la tabla y el permiso
-- de carga se controla en la app. Sólo lo que la app hace: leer, cargar y
-- eliminar. No hay UPDATE porque las entrevistas no se editan; si algún día se
-- agrega la edición hay que sumar su policy, o PostgREST no modifica ninguna
-- fila y tampoco da error.
ALTER TABLE seguimiento_general ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_seguimiento_general" ON seguimiento_general;
CREATE POLICY "anon_select_seguimiento_general" ON seguimiento_general
    FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "anon_insert_seguimiento_general" ON seguimiento_general;
CREATE POLICY "anon_insert_seguimiento_general" ON seguimiento_general
    FOR INSERT TO anon WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_seguimiento_general" ON seguimiento_general;
CREATE POLICY "anon_delete_seguimiento_general" ON seguimiento_general
    FOR DELETE TO anon USING (true);
