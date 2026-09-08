-- Migración: tabla seguimiento_conductores
-- Ejecutar una sola vez en el dashboard de Supabase → SQL Editor
--
-- Una fila = una entrevista de seguimiento del conductor (2° mes).
-- Escala 1-4 en todos los ítems cerrados:
--     Mala / Malo = 1 · Regular = 2 · Buena / Bueno = 3 · Muy buena / Muy bueno = 4
-- Los índices NO se guardan: se calculan en pandas (seguimiento.py) para que la
-- fórmula viva en un solo lugar.

CREATE TABLE IF NOT EXISTS seguimiento_conductores (
    -- ── Identificación (snapshot del padrón al momento de la entrevista) ──
    -- base / cargo / fecha_ingreso se desnormalizan a propósito: si mañana
    -- reasignan al conductor de Campana a Catamarca, no debe reescribirse la
    -- base de una entrevista de hace 6 meses.
    id                          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    legajo                      TEXT NOT NULL,
    apenom                      TEXT NOT NULL,
    empleador                   TEXT NOT NULL,
    base                        TEXT,          -- columna 'str' de MasterBus (operación)
    cargo                       TEXT,          -- 'CONDUCTORES' | 'CONDUCTOR'
    fecha_ingreso               DATE,
    fecha_entrevista            DATE NOT NULL,
    entrevistador               TEXT NOT NULL,
    fecha_proximo_seguimiento   DATE,
    registrado_por              TEXT,          -- usuario del dashboard que cargó la entrevista
    fecha_registro              TIMESTAMPTZ DEFAULT now(),

    -- ── Secciones 1-6: respuestas cerradas ──
    -- Escalas 1-4 (13 ítems, alimentan los índices)
    p01  SMALLINT CHECK (p01 BETWEEN 1 AND 4),
    p03  SMALLINT CHECK (p03 BETWEEN 1 AND 4),
    p04  SMALLINT CHECK (p04 BETWEEN 1 AND 4),
    p05  SMALLINT CHECK (p05 BETWEEN 1 AND 4),
    p06  SMALLINT CHECK (p06 BETWEEN 1 AND 4),
    p07  SMALLINT CHECK (p07 BETWEEN 1 AND 4),
    p08  SMALLINT CHECK (p08 BETWEEN 1 AND 4),
    p11  SMALLINT CHECK (p11 BETWEEN 1 AND 4),
    p12  SMALLINT CHECK (p12 BETWEEN 1 AND 4),
    p13  SMALLINT CHECK (p13 BETWEEN 1 AND 4),
    p14  SMALLINT CHECK (p14 BETWEEN 1 AND 4),
    p15  SMALLINT CHECK (p15 BETWEEN 1 AND 4),
    p20  SMALLINT CHECK (p20 BETWEEN 1 AND 4),

    -- Sí/No (TRUE = hay un problema → alerta)
    p09  BOOLEAN,
    p16  BOOLEAN,

    -- Categorías cerradas (lista fija en PREGUNTAS; 'Otro' se aclara en el _texto)
    p02  TEXT,
    p10  TEXT,
    p17  TEXT,
    p18  TEXT,
    p19  TEXT,

    -- ── Sección 7: autopercepción (el conductor se evalúa a sí mismo) ──
    auto_operaciones     SMALLINT CHECK (auto_operaciones     BETWEEN 1 AND 4),
    auto_seguridad_vial  SMALLINT CHECK (auto_seguridad_vial  BETWEEN 1 AND 4),
    auto_rrhh            SMALLINT CHECK (auto_rrhh            BETWEEN 1 AND 4),
    auto_mantenimiento   SMALLINT CHECK (auto_mantenimiento   BETWEEN 1 AND 4),

    -- ── Textuales ──
    p02_texto  TEXT,
    p09_texto  TEXT,   -- obligatorio a nivel app cuando p09 = TRUE
    p10_texto  TEXT,
    p16_texto  TEXT,   -- obligatorio a nivel app cuando p16 = TRUE
    p17_texto  TEXT,
    p18_texto  TEXT,
    p19_texto  TEXT,
    frases_destacadas  TEXT,

    -- ── Sección 8: conclusión ──
    fortalezas        TEXT,
    aspectos_mejorar  TEXT,
    compromisos       TEXT,

    -- Evita el duplicado por doble submit sin bloquear un seguimiento posterior
    -- del mismo conductor en otra fecha (la sección 8 pide "fecha de próximo
    -- seguimiento", o sea que las re-entrevistas están previstas).
    -- El legajo NO es único entre empresas: hay 15 conductores activos que
    -- comparten legajo con otro. Por eso la clave incluye el empleador.
    CONSTRAINT uq_seguimiento_legajo_empleador_fecha
        UNIQUE (legajo, empleador, fecha_entrevista)
);

CREATE INDEX IF NOT EXISTS idx_seguimiento_conductores_legajo
    ON seguimiento_conductores (legajo);
CREATE INDEX IF NOT EXISTS idx_seguimiento_conductores_fecha_entrevista
    ON seguimiento_conductores (fecha_entrevista DESC);

-- RLS: misma política que adelantos y descuentos (la anon key opera la tabla completa)
ALTER TABLE seguimiento_conductores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_all_seguimiento_conductores" ON seguimiento_conductores
    FOR ALL TO anon USING (true) WITH CHECK (true);
