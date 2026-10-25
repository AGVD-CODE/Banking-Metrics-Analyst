#!/usr/bin/env python3
"""
Funciones compartidas por los scripts del Estratega Bancario.

- Importa bcra_comun (copia incluida del skill bcra-oraculo): descarga y parseo
  de la API y de los PDF de "Información de Entidades Financieras" del BCRA.
- Salida JSON uniforme y manejo de errores.

No se ejecuta solo.
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def importar_bcra():
    """Devuelve el módulo bcra_comun (descarga y parseo de las fuentes del BCRA).

    Usa la copia incluida en scripts/ (la versión probada con este skill). Si se define
    BCRA_ORACULO_DIR con la carpeta de otro skill bcra-oraculo, usa la de ese skill.
    """
    env = os.environ.get('BCRA_ORACULO_DIR')
    if env:
        scripts = env if os.path.basename(env.rstrip('/')) == 'scripts' else os.path.join(env, 'scripts')
        if not os.path.exists(os.path.join(scripts, 'bcra_comun.py')):
            salida({'error': 'BCRA_ORACULO_DIR no tiene scripts/bcra_comun.py: %s' % env}, 2)
        sys.path.insert(0, scripts)
    elif AQUI not in sys.path:
        sys.path.insert(0, AQUI)
    import bcra_comun  # noqa: E402
    return bcra_comun


def salida(obj, codigo=0):
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=_json_default))
    sys.stdout.flush()
    sys.exit(codigo)


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if o != o else round(float(o), 6)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    return str(o)


def exigir_librerias():
    faltan = []
    for m in ('pandas', 'numpy', 'scipy', 'sklearn', 'statsmodels', 'matplotlib'):
        try:
            __import__(m)
        except ImportError:
            faltan.append(m)
    if faltan:
        salida({'error': 'Faltan librerías de Python: ' + ', '.join(faltan),
                'ayuda': 'pip install -r %s' % os.path.join(AQUI, 'requirements.txt')}, 2)


def mes_anterior(ym, n=1):
    a, m = int(ym[:4]), int(ym[5:7])
    m -= n
    while m <= 0:
        m += 12
        a -= 1
    return '%04d-%02d' % (a, m)


def meses_entre(desde, hasta):
    out, m = [], hasta
    while m >= desde:
        out.append(m)
        m = mes_anterior(m)
    return out[::-1]
