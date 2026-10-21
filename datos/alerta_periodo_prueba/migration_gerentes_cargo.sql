-- Migración: tabla gerentes_cargo
-- Ejecutar una sola vez en el dashboard de Supabase → SQL Editor

CREATE TABLE IF NOT EXISTS gerentes_cargo (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    cargo        TEXT NOT NULL UNIQUE,
    email_gerente TEXT NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- RLS: solo lectura pública (la anon key puede SELECT, no puede INSERT/UPDATE/DELETE)
ALTER TABLE gerentes_cargo ENABLE ROW LEVEL SECURITY;

CREATE POLICY "lectura_publica" ON gerentes_cargo
    FOR SELECT USING (true);

-- Datos iniciales: mapeo cargo → email de gerente responsable
INSERT INTO gerentes_cargo (cargo, email_gerente) VALUES
    ('ACTIVADOR',                                     'jcabral@masterbus.net'),
    ('ADMINISTRADOR DE COORDINACION IT',              'icarvajal@masterbus.net'),
    ('ADMINISTRATIVO',                                'dscirocco@masterbus.net'),
    ('ASISTENTE ADM DE INTENDENCIA',                  'ellanos@masterbus.net'),
    ('ASISTENTE ADM. DE RRHH',                        'ffillopski@masterbus.net'),
    ('ASISTENTE ADMINISTRATIVO DE PAÃOL',             'jcabral@masterbus.net'),
    ('ASISTENTE ADMINISTRATIVO DE SEGURIDAD VIAL',    'jcigna@masterbus.net'),
    ('ASISTENTE ADMINISTRATIVO DE TALLER',            'asalvetti@masterbus.net'),
    ('ASISTENTE BALANCE Y DOCUMENTACION DE BANCOS',   'dscirocco@masterbus.net'),
    ('ASISTENTE CONTABLE',                            'dscirocco@masterbus.net'),
    ('ASISTENTE DE ABASTECIMIENTO',                   'jcabral@masterbus.net'),
    ('ASISTENTE DE GESTION',                          'dscirocco@masterbus.net'),
    ('ASISTENTE DE LICITACIONES',                     'dscirocco@masterbus.net'),
    ('ASISTENTE DE NORMAS ISO',                       'talcantara@masterbus.net'),
    ('ASISTENTE DE SEGURIDAD INDUSTRIAL Y AMBIENTE',  'talcantara@masterbus.net'),
    ('ASISTENTE OPERATIVO',                           'mdepeon@masterbus.net'),
    ('ASISTENTE OPERATIVO DE SEGURIDAD VIAL',         'jcigna@masterbus.net'),
    ('BRIGADISTA',                                    'talcantara@masterbus.net'),
    ('CADETE',                                        'dscirocco@masterbus.net'),
    ('CELADOR',                                       'mdepeon@masterbus.net'),
    ('CHAPISTA',                                      'asalvetti@masterbus.net'),
    ('CHAPISTA (SALTA/CAT)',                          'asalvetti@masterbus.net'),
    ('CONDUCTOR',                                     'mdepeon@masterbus.net'),
    ('COORDINADOR DE BASES',                          'asalvetti@masterbus.net'),
    ('COORDINADOR DE IT FLOTA',                       'icarvajal@masterbus.net'),
    ('DESPACHANTE DE COMBUSTIBLE',                    'ellanos@masterbus.net'),
    ('DIAGRAMADOR DE TRAFICO',                        'mdepeon@masterbus.net'),
    ('ELECTRICISTA',                                  'asalvetti@masterbus.net'),
    ('ELECTRICISTA (SALTA/CAT)',                      'asalvetti@masterbus.net'),
    ('EMPLEADO PANIOL',                               'jcabral@masterbus.net'),
    ('ENCARGADO DE CUENTAS A PAGAR',                  'dscirocco@masterbus.net'),
    ('ENCARGADO DE FACTURACION',                      'dscirocco@masterbus.net'),
    ('ENCARGADO DE TESORERIA',                        'dscirocco@masterbus.net'),
    ('ENCARGADO IMPOSITIVO',                          'dscirocco@masterbus.net'),
    ('FORMADORES',                                    'jcigna@masterbus.net'),
    ('LAVADOR',                                       'ellanos@masterbus.net'),
    ('LIDER DE PAÃOL',                                'jcabral@masterbus.net'),
    ('LIQUIDADOR DE SUELDOS - GESTION DOC. EMPRESAS', 'ffillopski@masterbus.net'),
    ('MAESTRANZA',                                    'ellanos@masterbus.net'),
    ('MAESTRANZA OLAV',                               'ellanos@masterbus.net'),
    ('MECANICO',                                      'asalvetti@masterbus.net'),
    ('MECANICO (SALTA/CAT)',                          'asalvetti@masterbus.net'),
    ('OPERADOR',                                      'mdepeon@masterbus.net'),
    ('PAÃOLERO',                                      'jcabral@masterbus.net'),
    ('PROGRAMADOR OPERATIVO',                         'mdepeon@masterbus.net'),
    ('PROGRAMADOR/DESARROLLO',                        'mdepeon@masterbus.net'),
    ('RECEPCION',                                     'dscirocco@masterbus.net'),
    ('SEGURIDAD VIAL Y CAPACITACIONES',               'jcigna@masterbus.net'),
    ('SOPORTE ON SITE IT FLOTA',                      'icarvajal@masterbus.net'),
    ('SUPERVISOR ADM DE CARROCERIA',                  'asalvetti@masterbus.net'),
    ('SUPERVISOR DE CHAPA Y PINTURA',                 'asalvetti@masterbus.net'),
    ('SUPERVISOR DE ELECTRICISTAS',                   'asalvetti@masterbus.net'),
    ('SUPERVISOR DE OPERACIONES DE TALLER',           'asalvetti@masterbus.net'),
    ('SUPERVISOR DE PLANTA',                          'mdepeon@masterbus.net'),
    ('SUPERVISOR DE PLAYA',                           'ellanos@masterbus.net'),
    ('SUPERVISOR DE SUPERVISORES',                    'mdepeon@masterbus.net'),
    ('SUPERVISOR DE TALLER',                          'asalvetti@masterbus.net'),
    ('SUPERVISOR GENERAL',                            'asalvetti@masterbus.net'),
    ('SUPERVISOR OPERATIVO',                          'mdepeon@masterbus.net'),
    ('TALLER OLAV',                                   'asalvetti@masterbus.net')
ON CONFLICT (cargo) DO UPDATE SET email_gerente = EXCLUDED.email_gerente;
