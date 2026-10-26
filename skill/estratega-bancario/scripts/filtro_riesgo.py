#!/usr/bin/env python3
"""
Filtro de riesgo: usa el skill riesgo-bancario instalado (opcional).

Ubica riesgo-bancario, controla su versión y le pasa los argumentos. El primer argumento
elige qué correr: "panel" para su panel de riesgo y cualquier otro (salud, estres,
alertas, ranking) para su riesgo.py.

Uso:
    python3 filtro_riesgo.py panel --salida trabajo/panel_riesgo.csv
    python3 filtro_riesgo.py salud --panel trabajo/panel_riesgo.csv --entidad Macro
    python3 filtro_riesgo.py estres --panel trabajo/panel_riesgo.csv --escenario severo --entidad Macro
    python3 filtro_riesgo.py alertas --panel trabajo/panel_riesgo.csv --entidad Macro

Si riesgo-bancario no está instalado, responde con un JSON que explica qué instalar y cómo
seguir sin el filtro.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as cm  # noqa: E402


def main():
    r, encontrados = cm.ubicar_riesgo()
    if not r:
        req = '%d.%d' % cm.RIESGO_REQUERIDO
        cm.salida({
            'error': ('No está instalado el skill riesgo-bancario.' if not encontrados else
                      'La versión instalada de riesgo-bancario no es compatible: se necesita %d.x (%s o '
                      'posterior).' % (cm.RIESGO_REQUERIDO[0], req)),
            'encontradas': [{'carpeta': e['dir'], 'version': '.'.join(map(str, e['version'])) if e['version']
                             else 'sin archivo VERSION'} for e in encontrados],
            'ayuda': 'Instalar riesgo-bancario %s o posterior desde %s. Si está en otra carpeta, definir '
                     'RIESGO_DIR con esa carpeta.' % (req, cm.RIESGO_URL),
            'plan_b': 'Seguir sin filtro de riesgo: mirar a mano mora, cobertura, situación 2 y castigos '
                      '(bIrrec) del banco foco, y decir en la respuesta que las oportunidades no pasaron '
                      'por el filtro de riesgo.'}, 2)
    args = sys.argv[1:]
    if not args:
        cm.salida({'error': 'Falta el subcomando (panel, salud, estres, alertas o ranking)',
                   'riesgo_bancario': r['dir'], 'version': '.'.join(map(str, r['version']))}, 2)
    script = 'panel.py' if args[0] == 'panel' else 'riesgo.py'
    if args[0] == 'panel':
        args = args[1:]
    sys.exit(subprocess.run([sys.executable, os.path.join(r['dir'], 'scripts', script)] + args).returncode)


if __name__ == '__main__':
    main()
