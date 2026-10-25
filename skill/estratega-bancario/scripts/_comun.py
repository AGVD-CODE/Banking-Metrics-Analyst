#!/usr/bin/env python3
"""
Funciones compartidas por los scripts del Estratega Bancario.

- Ubica el skill bcra-oraculo instalado (la capa de datos del BCRA), controla que su
  versión sea compatible e importa su interfaz pública.
- Ubica el skill revisor-independiente instalado (la revisión antes de entregar) y
  controla su versión.
- Salida JSON uniforme y manejo de errores.

No se ejecuta solo.
"""
import glob
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))


# Versión de este skill (ver references/contrato.md).
VERSION = '1.2.0'

# Versión de bcra-oraculo con la que este skill es compatible: misma mayor y al menos esta menor.
ORACULO_REQUERIDO = (2, 1)
ORACULO_URL = 'https://github.com/AGVD-CODE/BCRA-Oracle/releases'

# Lo mismo para revisor-independiente (su versión está en el archivo VERSION de su raíz).
REVISOR_REQUERIDO = (1, 0)
REVISOR_URL = 'https://github.com/AGVD-CODE/Independent-Reviewer/releases'


def _version(ruta_comun):
    try:
        with open(ruta_comun, encoding='utf-8', errors='replace') as f:
            m = re.search(r'^VERSION\s*=\s*[\'"](\d+)\.(\d+)\.(\d+)[\'"]', f.read(), re.M)
        return tuple(int(x) for x in m.groups()) if m else None
    except OSError:
        return None


def _candidatos_oraculo():
    env = os.environ.get('BCRA_ORACULO_DIR')
    if env:
        yield env
    raiz = os.path.dirname(os.path.dirname(AQUI))  # carpeta donde están instalados los skills
    for n in ('bcra-oraculo', 'bcra-oracle-en'):
        yield os.path.join(raiz, n)
    for patron in ('~/.claude/skills/bcra-ora*', '~/.claude/skills/*/bcra-ora*', '/mnt/skills/*/bcra-ora*',
                   '/mnt/skills/*/*/bcra-ora*', '~/Library/Application Support/Claude/*/*/*/*/skills/bcra-ora*'):
        for d in sorted(glob.glob(os.path.expanduser(patron))):
            yield d


def ubicar_oraculo():
    """Busca el skill bcra-oraculo instalado (capa de datos) y controla que su versión sea compatible.

    Devuelve {'dir', 'scripts', 'version'}. Si no hay una versión compatible, termina con un JSON
    que explica qué instalar. BCRA_ORACULO_DIR permite indicar la carpeta a mano."""
    vistos, encontrados = set(), []
    for d in _candidatos_oraculo():
        d = os.path.abspath(d)
        scripts = d if os.path.basename(d) == 'scripts' else os.path.join(d, 'scripts')
        comun = os.path.join(scripts, 'bcra_comun.py')
        if scripts in vistos or not os.path.exists(comun):
            continue
        vistos.add(scripts)
        v = _version(comun)
        encontrados.append({'dir': os.path.dirname(scripts), 'scripts': scripts, 'version': v})
        if v and v[0] == ORACULO_REQUERIDO[0] and v[1] >= ORACULO_REQUERIDO[1]:
            return encontrados[-1]
    req = '%d.%d' % ORACULO_REQUERIDO
    if not encontrados:
        salida({'error': 'No está instalado el skill bcra-oraculo (capa de datos del BCRA), que este skill necesita.',
                'ayuda': 'Instalar bcra-oraculo %s o posterior (misma versión mayor) desde %s. Si está en otra '
                         'carpeta, definir BCRA_ORACULO_DIR con esa carpeta.' % (req, ORACULO_URL)}, 2)
    salida({'error': 'La versión instalada de bcra-oraculo no es compatible: se necesita %s.x (%s o posterior).'
                     % (ORACULO_REQUERIDO[0], req),
            'encontradas': [{'carpeta': e['dir'], 'version': '.'.join(map(str, e['version'])) if e['version']
                             else 'sin número de versión (anterior a 2.1)'} for e in encontrados],
            'ayuda': 'Actualizar bcra-oraculo desde %s' % ORACULO_URL}, 2)


def importar_bcra():
    """Importa bcra_comun desde el bcra-oraculo instalado (versión controlada).

    Este skill usa solo su interfaz pública (references/contrato.md de bcra-oraculo): CAMPOS, describir,
    GRUPOS, ALIAS, ALIAS_GRUPO, VACIAS y norm."""
    o = ubicar_oraculo()
    if o['scripts'] not in sys.path:
        sys.path.insert(0, o['scripts'])
    import bcra_comun  # noqa: E402
    return bcra_comun


def _candidatos_revisor():
    env = os.environ.get('REVISOR_DIR')
    if env:
        yield env
    yield os.path.join(os.path.dirname(os.path.dirname(AQUI)), 'revisor-independiente')
    for patron in ('~/.claude/skills/revisor-independiente', '~/.claude/skills/*/revisor-independiente',
                   '/mnt/skills/*/revisor-independiente', '/mnt/skills/*/*/revisor-independiente',
                   '~/Library/Application Support/Claude/*/*/*/*/skills/revisor-independiente'):
        for d in sorted(glob.glob(os.path.expanduser(patron))):
            yield d


def ubicar_revisor():
    """Busca el skill revisor-independiente instalado y controla que su versión sea compatible.

    Devuelve (revisor, encontrados): revisor es {'dir', 'version'} o None si no hay uno compatible;
    encontrados, todas las carpetas vistas con su versión. REVISOR_DIR permite indicar la carpeta."""
    vistos, encontrados = set(), []
    for d in _candidatos_revisor():
        d = os.path.abspath(d)
        if d in vistos or not os.path.exists(os.path.join(d, 'SKILL.md')):
            continue
        vistos.add(d)
        try:
            with open(os.path.join(d, 'VERSION'), encoding='utf-8') as f:
                m = re.match(r'\s*(\d+)\.(\d+)\.(\d+)', f.read())
            v = tuple(int(x) for x in m.groups()) if m else None
        except OSError:
            v = None
        encontrados.append({'dir': d, 'version': v})
        if v and v[0] == REVISOR_REQUERIDO[0] and v[1] >= REVISOR_REQUERIDO[1]:
            return encontrados[-1], encontrados
    return None, encontrados


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
