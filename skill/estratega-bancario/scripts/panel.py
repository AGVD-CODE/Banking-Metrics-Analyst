#!/usr/bin/env python3
"""
Panel de bancos (muchas entidades × muchos meses) para el análisis.

Lo arma el skill bcra-oraculo, la capa de datos (su script consultar_panel.py).
Este envoltorio ubica el oráculo instalado, controla que la versión sea compatible
y le pasa los mismos argumentos. Ver la ayuda completa con --help.

Uso:
    python3 panel.py --meses 60 --salida panel.csv
    python3 panel.py --desde 2016-01 --top 25 --salida panel_largo.csv
    python3 panel.py --meses 36 --historicas --salida panel.csv
    python3 panel.py --entidades Galicia Macro Santander BBVA --meses 24 --salida panel.csv
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as cm  # noqa: E402


def main():
    o = cm.ubicar_oraculo()
    script = os.path.join(o['scripts'], 'consultar_panel.py')
    if not os.path.exists(script):
        cm.salida({'error': 'El bcra-oraculo instalado (%s) no tiene consultar_panel.py' % o['dir'],
                   'ayuda': 'Actualizar bcra-oraculo desde %s' % cm.ORACULO_URL}, 2)
    sys.exit(subprocess.run([sys.executable, script] + sys.argv[1:]).returncode)


if __name__ == '__main__':
    main()
