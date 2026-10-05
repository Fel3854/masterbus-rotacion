-- Migración: tabla entrevistas_postulantes + permiso ver_postulantes
-- Ejecutar una sola vez en el dashboard de Supabase → SQL Editor
--
-- Una fila = una entrevista del registro FORM 045 02 (entrevistas a postulantes).
-- Nació como copia de consulta del registro que se cargaba en Access. Desde
-- migration_postulantes_edicion.sql el registro se carga y se corrige en el
-- dashboard, y Access quedó sólo como origen de lo histórico.
--
-- Los datos se guardan TAL CUAL se cargaron, con sus errores de tipeo. Lo
-- que ordena la consulta (familia de puesto, sector normalizado, entrevistador
-- unificado, veces que se presentó) se deriva en pandas (postulantes.py) y no
-- se guarda, para que las reglas vivan en un solo lugar.
--
-- OJO con `apto`: sólo dice algo cuando está en TRUE. Desde 2023 la casilla casi
-- no se tilda, así que FALSE significa "sin marcar", no "rechazado".

CREATE TABLE IF NOT EXISTS entrevistas_postulantes (
    numero_orden        INTEGER PRIMARY KEY,         -- «Número de orden»: el de Access, o el siguiente si se cargó acá
    entrevistador       TEXT,
    fecha               DATE,                        -- NULL si en Access estaba vacía o en fecha cero
    apellido            TEXT,
    nombres             TEXT,
    dni                 BIGINT,                      -- NULL si en Access venía 0 o vacío
    puesto              TEXT,                        -- «Puesto al que se postula», texto libre
    sector              TEXT,
    apto                BOOLEAN NOT NULL DEFAULT FALSE,
    motivo_rechazo      TEXT,
    observaciones       TEXT,
    importado_por       TEXT,                        -- usuario que subió el archivo que la creó o cambió
    fecha_importacion   TIMESTAMPTZ DEFAULT now(),   -- cuándo entró por primera vez
    fecha_actualizacion TIMESTAMPTZ DEFAULT now(),   -- última vez que cambió, por archivo o a mano
    editado_por         TEXT,                        -- quien la cargó o editó en el dashboard; NULL si sólo vino de un archivo
    fecha_edicion       TIMESTAMPTZ,                 -- cuándo fue esa carga o edición a mano
    anulada             BOOLEAN NOT NULL DEFAULT FALSE  -- baja sin borrar: no se ve ni cuenta, y se puede restaurar
);

-- ── RLS: acá la política NO es la misma que en adelantos o minutas ──
-- La app puede leer, agregar y actualizar, pero NO borrar: no hay política de
-- DELETE ni FOR ALL, así que RLS lo rechaza. Es el registro histórico de RRHH;
-- se suman entrevistas y se corrigen las que cambiaron, nunca se eliminan (una
-- cargada por error se anula). Purgar filas exige el SQL Editor de Supabase.
ALTER TABLE entrevistas_postulantes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_entrevistas_postulantes" ON entrevistas_postulantes
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_insert_entrevistas_postulantes" ON entrevistas_postulantes
    FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "anon_update_entrevistas_postulantes" ON entrevistas_postulantes
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- ── Permiso para ver la pestaña ──
-- Las notas del registro tienen datos delicados de postulantes, así que esta
-- sección rompe la regla general del dashboard ("todos ven todo"): sólo la ve
-- quien tenga este permiso. Ser admin no lo incluye.
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS ver_postulantes BOOLEAN NOT NULL DEFAULT FALSE;
