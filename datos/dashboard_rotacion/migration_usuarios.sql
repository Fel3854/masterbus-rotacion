-- Migración: tabla usuarios
-- Ejecutar una sola vez en el dashboard de Supabase → SQL Editor
--
-- Los usuarios dejan de vivir en el código (el dict USERS de auth.py) y pasan a
-- ser datos: un admin no puede editar auth.py desde la app, así que para dar de
-- alta a alguien sin tocar el repo los usuarios tienen que estar en la base.
--
-- Las contraseñas se guardan hasheadas con PBKDF2-HMAC-SHA256 y salt por
-- usuario, en el formato `pbkdf2_sha256$iteraciones$salt$hash` (ver usuarios.py).
-- Nunca en claro: ni el admin puede leer la contraseña de otro, sólo resetearla.

CREATE TABLE IF NOT EXISTS usuarios (
    usuario       TEXT PRIMARY KEY,      -- minúsculas, 3-20, [a-z0-9_.]
    nombre        TEXT NOT NULL,         -- nombre visible ("Lu", "Juan Cigna — Gte...")
    activo        BOOLEAN NOT NULL DEFAULT TRUE,

    -- Administrador: única cuenta que ve la auditoría y gestiona usuarios.
    -- NO da permisos de edición sobre los módulos de datos: administrar y
    -- operar se mantienen separados a propósito.
    es_admin      BOOLEAN NOT NULL DEFAULT FALSE,

    -- Permisos de edición por módulo. Todos VEN todo; estos flags sólo habilitan
    -- registrar/editar/eliminar. Excepción: edit_seguimiento además habilita
    -- leer las respuestas textuales de las entrevistas, que son confidenciales.
    edit_adelantos    BOOLEAN NOT NULL DEFAULT FALSE,
    edit_descuentos   BOOLEAN NOT NULL DEFAULT FALSE,
    edit_seguimiento  BOOLEAN NOT NULL DEFAULT FALSE,
    edit_minutas      BOOLEAN NOT NULL DEFAULT FALSE,

    password_hash TEXT NOT NULL,
    -- Se levanta al crear la cuenta y al resetear la contraseña: quien la fijó
    -- la conoce, así que no sirve como prueba de identidad hasta que el dueño
    -- la cambia. La app bloquea la navegación hasta que eso pase.
    debe_cambiar_password BOOLEAN NOT NULL DEFAULT TRUE,

    fecha_alta    TIMESTAMPTZ DEFAULT now(),
    creado_por    TEXT,
    ultimo_acceso TIMESTAMPTZ
);

-- RLS: misma política que adelantos, descuentos y seguimiento — la anon key
-- opera la tabla completa. La anon key vive sólo en los secrets del servidor
-- (Streamlit corre del lado del servidor, nunca la manda al navegador), así que
-- el nivel de confianza es el mismo que el del resto de la app.
--
-- Los hashes igual no se leen en las consultas normales: usuarios.COLUMNAS
-- excluye password_hash y sólo se pide al validar un login.
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_all_usuarios" ON usuarios
    FOR ALL TO anon USING (true) WITH CHECK (true);
