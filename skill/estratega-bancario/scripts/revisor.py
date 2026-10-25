#!/usr/bin/env python3
"""
Ubica el skill revisor-independiente instalado para el paso 7 (revisión antes de entregar).

Controla que su versión sea compatible y devuelve en JSON las rutas que hay que pasarle al
revisor: sus instrucciones, su lista general y la lista bancaria de este skill.

Uso:
    python3 revisor.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as cm  # noqa: E402

LISTA_BANCARIA = os.path.join(os.path.dirname(cm.AQUI), 'references', 'revision_bancaria.md')


def main():
    r, encontrados = cm.ubicar_revisor()
    if r:
        cm.salida({'revisor': r['dir'], 'version': '.'.join(map(str, r['version'])),
                   'instrucciones': os.path.join(r['dir'], 'SKILL.md'),
                   'lista_general': os.path.join(r['dir'], 'references', 'lista_general.md'),
                   'lista_dominio': LISTA_BANCARIA})
    req = '%d.%d' % cm.REVISOR_REQUERIDO
    cm.salida({
        'error': ('No está instalado el skill revisor-independiente.' if not encontrados else
                  'La versión instalada de revisor-independiente no es compatible: se necesita %d.x '
                  '(%s o posterior).' % (cm.REVISOR_REQUERIDO[0], req)),
        'encontradas': [{'carpeta': e['dir'], 'version': '.'.join(map(str, e['version'])) if e['version']
                         else 'sin archivo VERSION'} for e in encontrados],
        'ayuda': 'Instalar revisor-independiente %s o posterior desde %s. Si está en otra carpeta, definir '
                 'REVISOR_DIR con esa carpeta.' % (req, cm.REVISOR_URL),
        'plan_b': ('Revisión reducida: hacela vos con %s, recalculando los números clave desde trabajo/, y '
                   'escribí trabajo/revision.md con veredicto, críticos, importantes y menores. En la '
                   'respuesta final aclará que fue una revisión reducida y que conviene instalar el '
                   'revisor.' % LISTA_BANCARIA)}, 2)


if __name__ == '__main__':
    main()
