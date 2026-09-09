-- Migración: tabla minutas_reunion
-- Ejecutar una sola vez en el dashboard de Supabase → SQL Editor
--
-- Una fila = un ítem de acción salido de una reunión de RRHH.
-- El estado avanza en el tiempo: Pendiente → En curso → Completa.
-- "Vencida" NO es un estado: se deriva en pandas (minutas.py) de la fecha límite,
-- para que la regla viva en un solo lugar y no queden filas con un valor viejo.

CREATE TABLE IF NOT EXISTS minutas_reunion (
    id                   UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    fecha                DATE NOT NULL,              -- fecha de la reunión / del ítem
    tema                 TEXT NOT NULL,              -- tema o acción (título corto)
    descripcion          TEXT,                       -- detalle del tema o acción
    responsable          TEXT,                       -- quién lo tiene a cargo (texto libre)
    fecha_limite         DATE,                       -- vencimiento (opcional)
    estado               TEXT NOT NULL DEFAULT 'Pendiente'
                             CHECK (estado IN ('Pendiente', 'En curso', 'Completa')),
    registrado_por       TEXT,                       -- usuario del dashboard que la cargó
    fecha_registro       TIMESTAMPTZ DEFAULT now(),
    fecha_actualizacion  TIMESTAMPTZ DEFAULT now()   -- se pisa en cada update (ver trigger)
);

CREATE INDEX IF NOT EXISTS idx_minutas_reunion_estado
    ON minutas_reunion (estado);
CREATE INDEX IF NOT EXISTS idx_minutas_reunion_fecha_limite
    ON minutas_reunion (fecha_limite);

-- Mantiene fecha_actualizacion al día en cada UPDATE, sin depender de la app.
-- `SET search_path = ''` evita el warning de search_path mutable del linter de
-- Supabase; now() vive en pg_catalog, que siempre resuelve aunque el path quede vacío.
CREATE OR REPLACE FUNCTION set_minutas_fecha_actualizacion()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    NEW.fecha_actualizacion := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_minutas_fecha_actualizacion ON minutas_reunion;
CREATE TRIGGER trg_minutas_fecha_actualizacion
    BEFORE UPDATE ON minutas_reunion
    FOR EACH ROW EXECUTE FUNCTION set_minutas_fecha_actualizacion();

-- RLS: misma política que adelantos / descuentos / seguimiento (la anon key opera
-- la tabla completa; el permiso de edición se controla en la app, no en la base).
ALTER TABLE minutas_reunion ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_all_minutas_reunion" ON minutas_reunion
    FOR ALL TO anon USING (true) WITH CHECK (true);
