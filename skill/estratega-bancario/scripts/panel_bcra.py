#!/usr/bin/env python3
"""
Panel histórico de métricas bancarias: muchas entidades × muchos meses × muchos
campos, listo para análisis comparativo.

Usa bcra_comun.py (incluido, tomado del skill bcra-oraculo) para bajar y parsear la información oficial del BCRA
("Información de Entidades Financieras"):
- modo api: la API JSON del BCRA. Rápido, sin dependencias, pero solo 5
  períodos (3 últimos meses + 2 últimos diciembres).
- modo pdf: los PDF mensuales (cada uno trae 3 meses + 2 diciembres de TODAS
  las entidades). Da historia mensual desde 2014. Requiere pdftotext.
- modo auto (por defecto): pdf si el rango pedido excede lo que trae la API.

Uso:
    python3 panel_bcra.py --meses 36 --salida panel.csv                 # todos los bancos, 3 años
    python3 panel_bcra.py --top 20 --desde 2022-01 --salida panel.csv   # 20 mayores bancos por activo
    python3 panel_bcra.py --entidades Galicia Santander BBVA Macro Nacion --meses 24
    python3 panel_bcra.py --entidades privados --campos bPr_priv bDe_priv irr_cons roe
    python3 panel_bcra.py --modo api --salida foto.csv                  # foto actual, rápido

Entidades: nombres, alias o códigos del BCRA, o grupos: bancos (por
defecto: públicos + privados), privados, publicos, companias, todas. Siempre se
agregan los agregados oficiales del BCRA (sistema, publicos, privados, top10)
con tipo "grupo", para calcular cuotas de mercado sin sumar a mano.

Salida: CSV ancho (periodo, codigo, entidad, tipo, campo1, campo2, ...) y un
JSON por stdout con cobertura, unidades y avisos. Montos en millones de pesos
CORRIENTES de cada mes (no comparables en el tiempo sin deflactar).
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as cm  # noqa: E402

bc = cm.importar_bcra()

CAMPOS_DEFECTO = [
    # balance (millones de pesos corrientes; resultados acumulados del ejercicio)
    'bA', 'bEf', 'bTi', 'bPr', 'bPr_priv', 'bAdel', 'bDoc', 'bHip', 'bPrend', 'bPers', 'bPrev',
    'bP', 'bDe', 'bDe_priv', 'bCC', 'bCA', 'bPF', 'bPN', 'bRes', 'bIF', 'bEgF', 'bInc', 'bIS',
    'bES', 'bGA', 'bRM', 'bIG',
    # indicadores (%)
    'irr_tot', 'irr_priv', 'irr_cons', 'irr_com', 'prev_irr', 'part_cons', 'part_com', 'roe',
    'roa', 'tasa_prest', 'tasa_dep', 'apalancamiento', 'absorc_gastos', 'margen_fin_activo',
    'result_serv_activo', 'roa_adm', 'roa_inco', 'liq_amplia', 'dep_empleado', 'fin_empleado',
    'gpers_gadm',
    # cartera (situación de deudores)
    'tf_total', 'com_total', 'con_total', 'tf_s2', 'tf_irregular', 'con_s2', 'com_s2',
    # información adicional (trimestral) y cuentas sueldo (mensual)
    'cc', 'cah', 'cah_social', 'cprev', 'pla', 'tit', 'deb', 'emp', 'pf_ind', 'pf_emp', 'op_hip',
    'op_prend', 'remu', 'remu_emp',
]
SECCIONES_PDF = {'indicadores', 'balance', 'cartera', 'adicional', 'remuneraciones'}
GRUPOS_FIJOS = ['sistema', 'publicos', 'privados', 'top10']
TIPO_GRUPO = {'AAA10': 'publico', 'AAA20': 'privado', 'AAA30': 'compania'}
# Páginas que siguen a la de la ficha de cada entidad en el PDF
TITULOS_PAGINA = re.compile(r'^(EVOLUCI|INDICADORES|INFORMACI|ESTADO DE SITUACI|PAGO DE REMUN|'
                            r'SITUACI|COMPOSICI)', re.I)
HEADER = re.compile(r'^\s*(\d{5}) - (.+?)\s*$')


def tipos_por_codigo():
    tipos = {}
    for g, tipo in TIPO_GRUPO.items():
        for e in bc.nomina(g):
            tipos[e['codigo']] = (tipo, e['nombre'])
    return tipos


def elegir_entidades(pedidas, tipos, top):
    elegidas, avisos = {}, []
    claves = {'bancos': ('publico', 'privado'), 'privados': ('privado',),
              'publicos': ('publico',), 'companias': ('compania',),
              'todas': ('publico', 'privado', 'compania')}
    entidades = [{'codigo': c, 'nombre': n} for c, (_, n) in tipos.items()]
    for p in pedidas:
        k = bc.norm(p).lower()
        if k in claves:
            for c, (t, n) in tipos.items():
                if t in claves[k]:
                    elegidas[c] = n
            continue
        try:
            e = bc.resolver(p, entidades)
        except bc.ErrorFuente as err:
            avisos.append('%s: %s %s' % (p, err, getattr(err, 'extra', '') or ''))
            continue
        if e['tipo'] == 'grupo':
            avisos.append('%s es un grupo: los agregados ya se incluyen siempre' % p)
            continue
        elegidas[e['codigo']] = e['nombre']
    if top and len(elegidas) > top:
        def activo(c):
            r = bc.consultar(bc.codigo_api(c), {'balance'})
            return bc.ultimo_valor(r['campos'].get('bA', {}))[1] or 0
        res = bc.en_paralelo(activo, list(elegidas))
        orden = sorted([(c, v) for c, v in res if not isinstance(v, Exception)],
                       key=lambda x: -x[1])[:top]
        elegidas = {c: elegidas[c] for c, _ in orden}
    return elegidas, avisos


# ------------------------------------------------------------------ API

def via_api(codigos, campos):
    secs = sorted({bc.CAMPOS[k][0] for k in campos})
    res = bc.en_paralelo(lambda c: bc.consultar(bc.codigo_api(c), set(secs)), codigos)
    out, errores, actualizado = {}, {}, None
    for c, r in res:
        if isinstance(r, Exception):
            errores[str(c)] = str(r)
            continue
        out[c] = {k: dict(r['campos'].get(k) or {}) for k in campos}
        if r.get('actualizado'):
            actualizado = max(actualizado or '', r['actualizado'])
    return out, errores, actualizado


# ------------------------------------------------------------------ PDF

def bloques_pdf(ruta):
    """{codigo: texto de sus páginas} para todas las entidades del PDF (un solo pdftotext)."""
    r = subprocess.run(['pdftotext', '-layout', ruta, '-'], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=600)
    if r.returncode != 0:
        raise bc.ErrorFuente('pdftotext falló: ' + r.stderr.decode('utf-8', 'replace')[:300])
    pags = r.stdout.decode('utf-8', 'replace').split('\f')
    primera = [next((l.strip() for l in p.split('\n') if l.strip()), '') for p in pags]
    out, i = {}, 0
    while i < len(pags):
        m = HEADER.match(primera[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while j < len(pags) and j - i < 8 and not HEADER.match(primera[j]) \
                and TITULOS_PAGINA.match(primera[j]):
            j += 1
        out[int(m.group(1))] = '\f'.join(pags[i:j])
        i = j
    return out


def via_pdf(ym, codigos, grupos, campos, historicas=False, vigentes=(), solo=None):
    """Campos de todas las entidades y grupos pedidos en el PDF del mes ym.

    historicas: agregar también las entidades del PDF que ya no están vigentes
    (fusionadas, absorbidas o cerradas), para armar series pro forma.
    solo: si se indica, procesar únicamente esos códigos (sin grupos)."""
    try:
        ruta = bc.pdf_entidades(ym)
    except bc.NoEncontrado:
        ym = bc.mes_anterior(ym)  # el mes todavía no está publicado
        ruta = bc.pdf_entidades(ym)
    bloques = bloques_pdf(ruta)
    out, faltan, nombres_hist = {}, [], {}
    if solo is not None:
        codigos, grupos = [c for c in solo if c in bloques], []
    elif historicas:
        for c, txt in bloques.items():
            if c not in vigentes:
                m = HEADER.match(txt.lstrip().split('\n')[0])
                nombres_hist[c] = m.group(2).strip() if m else str(c)
        codigos = list(codigos) + sorted(nombres_hist)
    for c in codigos:
        if c not in bloques:
            faltan.append(c)
            continue
        r = bc.normalizar_pdf(bloques[c])
        out[c] = {k: r['campos'].get(k) or {} for k in campos}
    for g in grupos:
        try:
            texto, _ = bc.paginas_entidad_pdf(ruta, bc.resolver(g))
            r = bc.normalizar_pdf(texto)
            out[bc.GRUPOS[g][0]] = {k: r['campos'].get(k) or {} for k in campos}
        except bc.ErrorFuente as e:
            faltan.append('%s (%s)' % (g, e))
    return {'ym': ym, 'url': bc.PDF_ENTIDADES.format(ym=ym.replace('-', '')), 'datos': out,
            'faltan': faltan, 'historicas': nombres_hist}


def plan_pdfs(desde, hasta):
    """Un PDF cubre su mes y los dos anteriores."""
    plan, cubiertos = [], set()
    for m in reversed(cm.meses_entre(desde, hasta)):
        if m not in cubiertos:
            plan.append(m)
            cubiertos.update({m, cm.mes_anterior(m), cm.mes_anterior(m, 2)})
    return plan


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--entidades', nargs='+', default=['bancos'])
    ap.add_argument('--top', type=int, help='quedarse con las N mayores por activo')
    ap.add_argument('--campos', nargs='+', help='claves de campos del BCRA (references/diccionario_bcra.md; por defecto, un set amplio); "todos" = todas')
    ap.add_argument('--meses', type=int, default=24)
    ap.add_argument('--desde', help='YYYY-MM')
    ap.add_argument('--hasta', help='YYYY-MM (por defecto, el último publicado)')
    ap.add_argument('--modo', choices=['auto', 'api', 'pdf'], default='auto')
    ap.add_argument('--salida', default='panel.csv')
    ap.add_argument('--historicas', action='store_true',
                    help='incluir entidades ya no vigentes (fusionadas o cerradas) halladas en los PDF; '
                         'sirve para armar series pro forma con analizar.py proforma')
    a = ap.parse_args()

    t0 = time.time()
    if a.campos == ['todos']:
        campos = [k for k, v in bc.CAMPOS.items() if v[0] in SECCIONES_PDF]
    else:
        campos = a.campos or CAMPOS_DEFECTO
    desconocidos = [k for k in campos if k not in bc.CAMPOS]
    if desconocidos:
        cm.salida({'error': 'Campos desconocidos: %s' % desconocidos,
                   'ayuda': 'Ver references/diccionario_bcra.md'}, 2)

    tipos = tipos_por_codigo()
    elegidas, avisos = elegir_entidades(a.entidades, tipos, a.top)
    if not elegidas:
        cm.salida({'error': 'No quedó ninguna entidad', 'avisos': avisos}, 2)
    codigos = sorted(elegidas)
    grupos_api = [bc.GRUPOS[g][0] for g in GRUPOS_FIJOS]

    datos_api, errores_api, actualizado = via_api(codigos + grupos_api, campos)
    hasta = a.hasta or actualizado
    desde = a.desde or cm.mes_anterior(hasta, max(1, a.meses) - 1)
    periodos_api = sorted({p for d in datos_api.values() for s in d.values() for p in s})
    recientes = [p for p in periodos_api if p >= cm.mes_anterior(actualizado, 2)]
    necesita_pdf = any(m not in periodos_api for m in cm.meses_entre(desde, hasta))
    modo = a.modo
    if modo == 'auto':
        modo = 'pdf' if necesita_pdf else 'api'
    if modo == 'pdf' and not bc.hay_pdftotext():
        avisos.append('Falta pdftotext (poppler-utils): solo se usaron los 5 períodos de la API. '
                      'Instalar con apt-get install -y poppler-utils o brew install poppler.')
        modo = 'api'

    # Fusionar: PDF viejos -> PDF nuevos -> API (lo más reciente pisa revisiones)
    panel, pdfs, faltantes, historicas = {}, [], {}, {}

    def volcar(datos):
        for c, cs in datos.items():
            for k, serie in cs.items():
                for p, v in serie.items():
                    if desde <= p <= hasta:
                        panel.setdefault((p, c), {})[k] = v

    if modo == 'pdf':
        plan = [m for m in plan_pdfs(desde, hasta) if not set(
            [m, cm.mes_anterior(m), cm.mes_anterior(m, 2)]) <= set(recientes)]
        res = bc.en_paralelo(lambda m: via_pdf(m, codigos, GRUPOS_FIJOS, campos, a.historicas,
                                               set(tipos)), plan, workers=4)
        ok = sorted([r for _, r in res if not isinstance(r, Exception)], key=lambda r: r['ym'])
        for m, r in res:
            if isinstance(r, Exception):
                faltantes['pdf_' + m] = str(r)
        for r in ok:
            volcar(r['datos'])
            pdfs.append(r['url'])
            for c, n in r['historicas'].items():
                historicas.setdefault(c, {'nombre': n, 'ultimo_pdf': r['ym']})
                historicas[c]['ultimo_pdf'] = max(historicas[c]['ultimo_pdf'], r['ym'])
        # Una entidad que deja de reportar entre dos PDF del plan pierde sus últimos meses:
        # se bajan los PDF intermedios solo para ella.
        extra = {}
        for c, h in historicas.items():
            for k in (1, 2):
                m = cm.mes_anterior(h['ultimo_pdf'], -k)
                if m <= hasta and m not in plan:
                    extra.setdefault(m, set()).add(c)
        if extra:
            res2 = bc.en_paralelo(lambda m: via_pdf(m, [], [], campos, solo=sorted(extra[m])),
                                  sorted(extra), workers=4)
            for m, r in sorted(res2, key=lambda x: x[0]):
                if not isinstance(r, Exception):
                    volcar(r['datos'])
                    pdfs.append(r['url'])
            if r['faltan']:
                faltantes[r['ym']] = r['faltan']
    volcar(datos_api)

    nombres = dict(elegidas)
    nombres.update({c: h['nombre'] for c, h in historicas.items()})
    for g in GRUPOS_FIJOS:
        nombres[bc.GRUPOS[g][0]] = bc.GRUPOS[g][1]
    filas = sorted(panel.items(), key=lambda x: (x[0][0], str(x[0][1])))
    with open(a.salida, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['periodo', 'codigo', 'entidad', 'tipo'] + campos)
        for (p, c), vals in filas:
            tipo = 'grupo' if isinstance(c, str) else ('historica' if c in historicas
                                                       else tipos.get(c, ('', ''))[0])
            w.writerow([p, c, nombres.get(c, c), tipo] + ['' if vals.get(k) is None else vals[k]
                                                          for k in campos])

    periodos = sorted({p for p, _ in panel})
    cobertura = {}
    n_ent = len(codigos)
    for k in campos:
        con = sum(1 for (p, c), v in panel.items() if not isinstance(c, str) and v.get(k) is not None)
        meses_k = sorted({p for (p, c), v in panel.items() if v.get(k) is not None})
        info = bc.describir(k)
        cobertura[k] = {'desc': info['desc'], 'unidad': info['unidad'],
                        'meses_con_dato': len(meses_k),
                        'pct_celdas': round(100.0 * con / max(1, n_ent * len(periodos)), 1)}
    if modo == 'api' and necesita_pdf:
        avisos.append('Con la API solo hay %s: no es una serie mensual continua.' % periodos_api)
    avisos.append('Supervivencia: solo entidades vigentes hoy; las fusionadas o cerradas no están.')
    out = {'archivo': os.path.abspath(a.salida), 'modo': modo, 'desde': periodos[0] if periodos else None,
           'hasta': periodos[-1] if periodos else None, 'periodos': len(periodos),
           'entidades': len(codigos), 'grupos': GRUPOS_FIJOS,
           'lista_entidades': {str(c): '%s (%s)' % (elegidas[c], tipos.get(c, ('?',))[0]) for c in codigos},
           'campos': cobertura,
           'fuente': 'BCRA — Información de Entidades Financieras (%s)' %
                     ('PDF mensuales + API' if modo == 'pdf' else 'API'),
           'pdfs': pdfs, 'segundos': round(time.time() - t0, 1),
           'notas': ['Montos en millones de pesos corrientes: deflactar antes de comparar en el tiempo.',
                     'Resultados (bRes, bIF, bEgF, bInc, bIS, bES, bGA, bRM) acumulados desde el inicio '
                     'del ejercicio.',
                     'Información adicional (cc, cah, pla, tit, deb, emp, pf_*, op_*) es trimestral.',
                     'Celda vacía = sin dato publicado (nunca cero).']}
    if historicas:
        for c, h in historicas.items():
            ult = max([p for (p, cc) in panel if cc == c] or [None])
            h['ultimo_mes_con_dato'] = ult
        out['entidades_historicas'] = {str(c): h for c, h in historicas.items()}
        out['nota_historicas'] = ('Entidades que reportaron en el período y hoy no están vigentes (tipo '
                                  '"historica"). Si una fue absorbida por una entidad del panel, usar '
                                  'analizar.py proforma para sumarla hacia atrás.')
    if avisos:
        out['avisos'] = avisos
    if errores_api:
        out['errores_api'] = errores_api
    if faltantes:
        out['faltantes'] = faltantes
    cm.salida(out)


if __name__ == '__main__':
    bc.ejecutar(main)
