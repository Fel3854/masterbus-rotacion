-- Migración: carga y edición de Postulantes en el dashboard
-- Ejecutar una sola vez en el dashboard de Supabase → SQL Editor
-- (después de migration_entrevistas_postulantes.sql y migration_usuarios.sql)
--
-- Hasta acá el registro FORM 045 02 se cargaba en Access y esta base era su
-- copia de consulta. Desde esta migración el dashboard ES el registro: las
-- entrevistas se cargan, se corrigen y se anulan acá, y Access deja de usarse.
--
-- Es aditiva: no cambia ni borra nada de lo que ya está, así que se puede
-- aplicar antes de publicar el código nuevo. Al revés no: el código nuevo pide
-- estas columnas por nombre y sin ellas no carga ni el login.

-- ── 1. Rastro de lo que se cargó o editó a mano, y anulación ──
-- `editado_por` y `fecha_edicion` se sellan sólo cuando alguien carga o edita
-- la entrevista en el dashboard; quedan en NULL en las que sólo vinieron de un
-- archivo. Con eso una importación sabe qué filas NO tiene que pisar.
--
-- `anulada` es la baja del registro: la entrevista deja de verse y de contar,
-- pero la fila sigue en la tabla y se puede restaurar. Nunca se borra.
ALTER TABLE entrevistas_postulantes
    ADD COLUMN IF NOT EXISTS editado_por   TEXT,
    ADD COLUMN IF NOT EXISTS fecha_edicion TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS anulada       BOOLEAN NOT NULL DEFAULT FALSE;

-- ── 2. Permiso de carga y edición ──
-- `ver_postulantes` pasa a ser sólo de lectura. Quien hoy lo tiene ya podía
-- actualizar el registro desde Access, así que arranca con el permiso nuevo:
-- nadie pierde ni gana nada el día del cambio. Va adentro del IF para que
-- volver a correr la migración no le devuelva el permiso a quien el admin se
-- lo haya sacado después.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'usuarios'
          AND column_name = 'edit_postulantes'
    ) THEN
        ALTER TABLE public.usuarios
            ADD COLUMN edit_postulantes BOOLEAN NOT NULL DEFAULT FALSE;
        UPDATE public.usuarios SET edit_postulantes = TRUE WHERE ver_postulantes;
    END IF;
END $$;

-- ── 3. Historial: la versión anterior de cada entrevista modificada ──
-- Sin Access, esta base es la única copia de un registro que arranca en 2007.
-- Una edición en lote equivocada pisaría datos que no están en ningún otro
-- lado, así que cada UPDATE deja acá la fila tal como estaba antes.
--
-- Lo escribe un trigger, no la app: así queda registrado cualquier camino
-- (edición, edición en lote, importación) y no depende de que el código se
-- acuerde. Restaurar es, por ahora, a mano desde el SQL Editor.
CREATE TABLE IF NOT EXISTS entrevistas_postulantes_historial (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_orden  INTEGER NOT NULL,
    cambiado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    cambiado_por  TEXT,                    -- quién hizo el cambio que la reemplazó
    fila_anterior JSONB NOT NULL           -- la fila completa, como estaba
);

CREATE INDEX IF NOT EXISTS entrevistas_postulantes_historial_numero
    ON entrevistas_postulantes_historial (numero_orden, cambiado_en);

-- RLS activado y SIN policies, a propósito: la app (anon key) no puede leer ni
-- escribir esta tabla. Tiene las mismas notas delicadas que el registro, y un
-- historial que el que edita puede corregir no sirve como respaldo. Sólo entra
-- el trigger de abajo y quien use la service key.
ALTER TABLE entrevistas_postulantes_historial ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON entrevistas_postulantes_historial FROM anon, authenticated;

-- SECURITY DEFINER: corre con los permisos del dueño, porque el rol de la app
-- no puede insertar en el historial. `search_path` vacío para que no se pueda
-- desviar a otra tabla con el mismo nombre.
CREATE OR REPLACE FUNCTION public.guardar_version_entrevista()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    INSERT INTO public.entrevistas_postulantes_historial
        (numero_orden, cambiado_por, fila_anterior)
    VALUES (
        OLD.numero_orden,
        -- Una edición a mano mueve `fecha_edicion`; una importación, no.
        CASE WHEN NEW.fecha_edicion IS DISTINCT FROM OLD.fecha_edicion
             THEN NEW.editado_por ELSE NEW.importado_por END,
        to_jsonb(OLD)
    );
    RETURN NEW;
END;
$$;

-- Sólo cuando cambia un dato de la entrevista: un UPDATE que deja todo igual
-- no agrega una versión idéntica a la anterior.
DROP TRIGGER IF EXISTS guardar_version_entrevista ON entrevistas_postulantes;
CREATE TRIGGER guardar_version_entrevista
    BEFORE UPDATE ON entrevistas_postulantes
    FOR EACH ROW
    WHEN ((OLD.entrevistador, OLD.fecha, OLD.apellido, OLD.nombres, OLD.dni,
           OLD.puesto, OLD.sector, OLD.apto, OLD.motivo_rechazo,
           OLD.observaciones, OLD.anulada)
          IS DISTINCT FROM
          (NEW.entrevistador, NEW.fecha, NEW.apellido, NEW.nombres, NEW.dni,
           NEW.puesto, NEW.sector, NEW.apto, NEW.motivo_rechazo,
           NEW.observaciones, NEW.anulada))
    EXECUTE FUNCTION public.guardar_version_entrevista();
