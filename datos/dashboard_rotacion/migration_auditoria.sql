-- Migración: tabla auditoria
-- Ejecutar una sola vez en el dashboard de Supabase → SQL Editor
--
-- Una fila = un movimiento de un usuario en el dashboard.
-- Registra altas, bajas, cambios, exportaciones, accesos a datos sensibles e
-- ingresos/salidas de sesión.
--
-- NO guarda contenido confidencial: del Seguimiento se registra que alguien
-- abrió o exportó una entrevista, nunca lo que el conductor respondió. Si el
-- textual se copiara acá, el permiso que lo protege sería decorativo.

CREATE TABLE IF NOT EXISTS auditoria (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    fecha        TIMESTAMPTZ NOT NULL DEFAULT now(),   -- en UTC; se muestra en hora AR
    usuario      TEXT NOT NULL,        -- clave de USERS ('lu', 'rrhh', ...)
    nombre       TEXT,                 -- nombre visible al momento del hecho
    modulo       TEXT NOT NULL,        -- adelantos | descuentos | seguimiento | minutas | sesion
    accion       TEXT NOT NULL,        -- alta | baja | cambio | export | lectura | login | logout | login_fallido
    detalle      TEXT,                 -- resumen legible del movimiento
    registro_id  TEXT,                 -- id de la fila afectada, si aplica
    datos        JSONB                 -- contexto extra (montos, legajo, cuotas)
);

CREATE INDEX IF NOT EXISTS idx_auditoria_fecha   ON auditoria (fecha DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria (usuario);
CREATE INDEX IF NOT EXISTS idx_auditoria_modulo  ON auditoria (modulo);

-- ── RLS: acá la política NO es la misma que en el resto de las tablas ──
-- Las demás tablas dan FOR ALL a la anon key. Esta es append-only a propósito:
-- INSERT y SELECT sí, UPDATE y DELETE no. Sin política que los habilite, RLS
-- los rechaza. Un registro de control que el propio auditado puede borrar o
-- editar desde la app no controla nada.
--
-- Corregir o purgar el historial requiere entrar al SQL Editor de Supabase con
-- la service key, que es exactamente la fricción que se busca.
ALTER TABLE auditoria ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_insert_auditoria" ON auditoria
    FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "anon_select_auditoria" ON auditoria
    FOR SELECT TO anon USING (true);
