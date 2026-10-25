#!/usr/bin/env python3
"""
Series macroeconómicas de Argentina en frecuencia mensual, listas para cruzar
con métricas bancarias.

Fuentes (todas oficiales y en vivo):
- INDEC: IPC Nacional (CSV), nivel general y núcleo.
- BCRA: API de Estadísticas v4 (tipo de cambio, tasas, reservas, préstamos y
  depósitos del sistema por línea, UVA, CER, expectativas de inflación REM).
- datos.gob.ar: API de Series de Tiempo (EMAE, salarios, RIPTE, desocupación,
  PBI, ventas de supermercados con tarjeta).

Uso:
    python3 macro_ar.py --catalogo                       # alias disponibles
    python3 macro_ar.py --desde 2019-01 --salida macro.csv
    python3 macro_ar.py --series ipc emae salario_real badlar --desde 2022-01 --salida macro.csv
    python3 macro_ar.py --buscar "prendarios"            # busca en BCRA y datos.gob.ar
    python3 macro_ar.py --series ipc --bcra-id 1126 --datos-id 89.1_TS_INTEIOS_0_M_32 --salida m.csv

Salida: CSV con una fila por mes (columna `periodo` YYYY-MM) y una columna por
serie, más un JSON por stdout con unidad, fuente, agregación y último dato de
cada serie. Las series diarias se llevan a mes con fin de mes (stocks) o
promedio (tasas y tipo de cambio). Las trimestrales quedan en el último mes de
cada trimestre (sin interpolar).
"""
import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import concurrent.futures as cf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as cm  # noqa: E402

UA = 'Mozilla/5.0 (compatible; estratega-bancario/1.0)'
BCRA_API = 'https://api.bcra.gob.ar/estadisticas/v4.0/monetarias'
DATOS_API = 'https://apis.datos.gob.ar/series/api/series/'
DATOS_BUSCAR = 'https://apis.datos.gob.ar/series/api/search/'
INDEC_IPC = 'https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv'

# alias: (fuente, id, descripción, unidad, agregación mensual)
# agregación: 'fin' (último dato del mes), 'prom' (promedio del mes), 'mes' (ya mensual)
CATALOGO = {
    # Precios
    'ipc': ('indec', 'Nivel general', 'IPC Nacional nivel general (dic-2016=100)', 'índice', 'mes'),
    'ipc_nucleo': ('indec', 'Núcleo', 'IPC Nacional núcleo (dic-2016=100)', 'índice', 'mes'),
    'cer': ('bcra', 30, 'Coeficiente de Estabilización de Referencia (CER)', 'índice', 'fin'),
    'uva': ('bcra', 31, 'Unidad de Valor Adquisitivo (UVA)', 'pesos', 'fin'),
    'expectativa_inflacion': ('bcra', 29, 'REM: mediana de inflación esperada próximos 12 meses', '%', 'mes'),
    # Tipo de cambio y sector externo
    'tc_mayorista': ('bcra', 5, 'Tipo de cambio mayorista de referencia (Com. A 3500), promedio', 'ARS/USD', 'prom'),
    'tc_minorista': ('bcra', 4, 'Tipo de cambio minorista promedio vendedor, promedio', 'ARS/USD', 'prom'),
    'reservas': ('bcra', 1, 'Reservas internacionales del BCRA, fin de mes', 'millones de USD', 'fin'),
    # Tasas
    'badlar': ('bcra', 7, 'Tasa BADLAR bancos privados (plazo fijo > $1M, 30-35 días), promedio', '% TNA', 'prom'),
    'tasa_pf30': ('bcra', 12, 'Tasa de depósitos a 30 días, promedio', '% TNA', 'prom'),
    'tasa_personales': ('bcra', 14, 'Tasa de préstamos personales, promedio', '% TNA', 'prom'),
    'tasa_adelantos': ('bcra', 13, 'Tasa de adelantos en cuenta corriente, promedio', '% TNA', 'prom'),
    'tasa_caja_ahorro': ('bcra', 1203, 'Tasa de depósitos en caja de ahorros (pesos), promedio', '% TNA', 'prom'),
    # Dinero y crédito del sistema (pesos, millones, fin de mes)
    'base_monetaria': ('bcra', 15, 'Base monetaria, fin de mes', 'millones de pesos', 'fin'),
    'prest_priv_total': ('bcra', 26, 'Préstamos al sector privado (pesos + dólares en pesos), fin de mes', 'millones de pesos', 'fin'),
    'prest_priv_pesos': ('bcra', 117, 'Préstamos al sector privado en pesos, fin de mes', 'millones de pesos', 'fin'),
    'prest_priv_usd': ('bcra', 125, 'Préstamos al sector privado en dólares, fin de mes', 'millones de USD', 'fin'),
    'prest_adelantos': ('bcra', 110, 'Préstamos en pesos: adelantos, fin de mes', 'millones de pesos', 'fin'),
    'prest_documentos': ('bcra', 111, 'Préstamos en pesos: documentos, fin de mes', 'millones de pesos', 'fin'),
    'prest_hipotecarios': ('bcra', 112, 'Préstamos en pesos: hipotecarios, fin de mes', 'millones de pesos', 'fin'),
    'prest_prendarios': ('bcra', 113, 'Préstamos en pesos: prendarios, fin de mes', 'millones de pesos', 'fin'),
    'prest_personales': ('bcra', 114, 'Préstamos en pesos: personales, fin de mes', 'millones de pesos', 'fin'),
    'prest_tarjetas': ('bcra', 115, 'Préstamos en pesos: tarjetas de crédito, fin de mes', 'millones de pesos', 'fin'),
    'dep_priv_pesos': ('bcra', 100, 'Depósitos del sector privado en pesos, fin de mes', 'millones de pesos', 'fin'),
    'dep_priv_cc': ('bcra', 94, 'Depósitos privados en cuenta corriente (pesos), fin de mes', 'millones de pesos', 'fin'),
    'dep_priv_ca': ('bcra', 95, 'Depósitos privados en caja de ahorros (pesos), fin de mes', 'millones de pesos', 'fin'),
    'dep_priv_pf': ('bcra', 96, 'Depósitos privados a plazo no ajustables (pesos), fin de mes', 'millones de pesos', 'fin'),
    'dep_priv_uva': ('bcra', 97, 'Depósitos privados a plazo ajustables por CER/UVA, fin de mes', 'millones de pesos', 'fin'),
    'dep_priv_usd': ('bcra', 108, 'Depósitos del sector privado en dólares, fin de mes', 'millones de USD', 'fin'),
    # Actividad, empleo e ingresos
    'emae': ('datos', '143.3_NO_PR_2004_A_21', 'EMAE original (2004=100)', 'índice', 'mes'),
    'emae_desest': ('datos', '143.3_NO_PR_2004_A_31', 'EMAE desestacionalizado (2004=100)', 'índice', 'mes'),
    'pbi_real': ('datos', '9.2_PP2_2004_T_16', 'PIB a precios constantes de 2004 (trimestral)', 'millones de pesos de 2004', 'mes'),
    'salarios': ('datos', '149.1_TL_INDIIOS_OCTU_0_21', 'Índice de salarios INDEC (oct-2016=100)', 'índice', 'mes'),
    'salarios_registrados': ('datos', '149.1_TL_REGIADO_OCTU_0_16', 'Índice de salarios INDEC, empleo registrado', 'índice', 'mes'),
    'ripte': ('datos', '158.1_REPTE_0_0_5', 'RIPTE: remuneración promedio de trabajadores estables', 'pesos', 'mes'),
    'desocupacion': ('datos', '42.3_EPH_PUNTUATAL_0_M_30', 'Tasa de desocupación EPH (trimestral)', '%', 'mes'),
    'super_tarjeta_credito': ('datos', '455.1_TARJETAS_CITO_0_M_16_85', 'Ventas en supermercados pagadas con tarjeta de crédito', 'miles de pesos corrientes', 'mes'),
}

# Derivadas: se calculan si están sus insumos (se agregan los insumos automáticamente)
DERIVADAS = {
    'inflacion_m': (['ipc'], 'Inflación mensual (CALCULADO con IPC)', '%'),
    'inflacion_ia': (['ipc'], 'Inflación interanual (CALCULADO con IPC)', '%'),
    'salario_real': (['salarios', 'ipc'], 'Salario real: índice de salarios / IPC (CALCULADO, base primer mes = 100)', 'índice'),
    'tasa_real_pf': (['tasa_pf30', 'ipc'], 'Tasa real ex post de plazo fijo 30 días, anualizada (CALCULADO)', '%'),
    'tasa_real_personales': (['tasa_personales', 'ipc'], 'Tasa real ex post de préstamos personales, anualizada (CALCULADO)', '%'),
    'tc_real': (['tc_mayorista', 'ipc'], 'Tipo de cambio mayorista deflactado por IPC local (CALCULADO, base primer mes = 100; aproximación sin inflación externa)', 'índice'),
    'emae_ia': (['emae'], 'EMAE: variación interanual (CALCULADO)', '%'),
    'brecha_minorista': (['tc_minorista', 'tc_mayorista'], 'Brecha minorista/mayorista (CALCULADO)', '%'),
}

POR_DEFECTO = ['ipc', 'inflacion_m', 'inflacion_ia', 'expectativa_inflacion', 'tc_mayorista', 'tc_real',
               'reservas', 'badlar', 'tasa_pf30', 'tasa_personales', 'tasa_real_pf',
               'tasa_real_personales', 'emae', 'emae_desest', 'emae_ia', 'salarios',
               'salario_real', 'desocupacion', 'prest_priv_pesos', 'prest_priv_usd',
               'prest_personales', 'prest_tarjetas', 'prest_hipotecarios', 'prest_prendarios',
               'prest_documentos', 'prest_adelantos', 'dep_priv_pesos', 'dep_priv_usd',
               'dep_priv_pf', 'dep_priv_ca', 'uva']


class SinRed(Exception):
    pass


def http(url, timeout=60, intentos=3):
    ultimo = None
    for _ in range(intentos):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            ultimo = e
    if 'Name or service not known' in str(ultimo) or 'nodename nor servname' in str(ultimo) \
            or 'Tunnel connection failed' in str(ultimo) or '403' in str(ultimo):
        raise SinRed('%s: %s' % (url.split('/')[2], ultimo))
    raise RuntimeError('Falló %s: %s' % (url, ultimo))


# ---------------------------------------------------------------- fuentes

def serie_bcra(idv, desde):
    """{fecha 'YYYY-MM-DD': valor} paginando la API v4 del BCRA."""
    out, offset = {}, 0
    while True:
        q = urllib.parse.urlencode({'desde': desde + '-01', 'limit': 3000, 'offset': offset})
        d = json.loads(http('%s/%s?%s' % (BCRA_API, idv, q)))
        res = d.get('results') or []
        det = res[0].get('detalle', []) if res else []
        for x in det:
            if x.get('valor') is not None:
                out[x['fecha']] = float(x['valor'])
        total = d.get('metadata', {}).get('resultset', {}).get('count', 0)
        offset += 3000
        if offset >= total or not det:
            break
    return out


def serie_datos(ids, desde):
    """{id: {fecha: valor}} desde la API de series de datos.gob.ar (hasta 40 ids por consulta)."""
    q = urllib.parse.urlencode({'ids': ','.join(ids), 'start_date': desde, 'limit': 5000,
                                'format': 'json'})
    d = json.loads(http(DATOS_API + '?' + q))
    if 'errors' in d:
        raise RuntimeError('datos.gob.ar: %s' % d['errors'])
    out = {i: {} for i in ids}
    for fila in d.get('data', []):
        f = fila[0]
        for i, v in zip(ids, fila[1:]):
            if v is not None:
                out[i][f] = float(v)
    return out


def serie_indec_ipc():
    """{'Nivel general': {YYYY-MM: índice}, 'Núcleo': {...}} del CSV del INDEC (Nacional)."""
    raw = http(INDEC_IPC, timeout=120).decode('latin-1')
    out = {'Nivel general': {}, 'Núcleo': {}}
    for fila in csv.reader(io.StringIO(raw), delimiter=';'):
        if len(fila) < 8 or fila[0] == 'Codigo':
            continue
        cod, desc, _, per, ind = fila[0], fila[1], fila[2], fila[3], fila[4]
        region = fila[7].strip()
        if region != 'Nacional':
            continue
        clave = 'Nivel general' if cod.strip() == '0' else ('Núcleo' if desc.strip().lower().startswith('n') and 'cleo' in desc.lower() else None)
        if not clave or not per.strip().isdigit():
            continue
        try:
            v = float(ind.replace(',', '.'))
        except ValueError:
            continue
        out[clave]['%s-%s' % (per[:4], per[4:6])] = v
    return out


def a_mensual(diaria, modo):
    por_mes = {}
    for f in sorted(diaria):
        por_mes.setdefault(f[:7], []).append(diaria[f])
    if modo == 'prom':
        return {m: sum(v) / len(v) for m, v in por_mes.items()}
    return {m: v[-1] for m, v in por_mes.items()}  # 'fin' o 'mes'


# ---------------------------------------------------------------- derivadas

def calcular_derivadas(tabla, pedidas, meta):
    meses = sorted(tabla)

    def col(k):
        return {m: tabla[m].get(k) for m in meses}

    ipc = col('ipc')
    infl = {}
    for i, m in enumerate(meses):
        if i and ipc[m] and ipc[meses[i - 1]]:
            infl[m] = ipc[m] / ipc[meses[i - 1]] - 1
    for k in pedidas:
        serie = {}
        if k == 'inflacion_m':
            serie = {m: 100 * v for m, v in infl.items()}
        elif k == 'inflacion_ia':
            for m in meses:
                m12 = cm.mes_anterior(m, 12)
                if ipc.get(m) and ipc.get(m12):
                    serie[m] = 100 * (ipc[m] / ipc[m12] - 1)
        elif k in ('salario_real', 'tc_real'):
            base = 'salarios' if k == 'salario_real' else 'tc_mayorista'
            num = col(base)
            pares = [(m, num[m] / ipc[m]) for m in meses if num.get(m) and ipc.get(m)]
            if pares:
                b = pares[0][1]
                serie = {m: 100 * v / b for m, v in pares}
        elif k in ('tasa_real_pf', 'tasa_real_personales'):
            t = col('tasa_pf30' if k == 'tasa_real_pf' else 'tasa_personales')
            for m in meses:
                if t.get(m) is not None and m in infl:
                    mensual = (1 + t[m] / 100 * 30 / 365) / (1 + infl[m]) - 1
                    serie[m] = 100 * ((1 + mensual) ** 12 - 1)
        elif k == 'emae_ia':
            e = col('emae')
            for m in meses:
                m12 = cm.mes_anterior(m, 12)
                if e.get(m) and e.get(m12):
                    serie[m] = 100 * (e[m] / e[m12] - 1)
        elif k == 'brecha_minorista':
            a, b = col('tc_minorista'), col('tc_mayorista')
            serie = {m: 100 * (a[m] / b[m] - 1) for m in meses if a.get(m) and b.get(m)}
        for m, v in serie.items():
            tabla[m][k] = v
        desc, unidad = DERIVADAS[k][1], DERIVADAS[k][2]
        meta[k] = {'desc': desc, 'unidad': unidad, 'fuente': 'CALCULADO', 'agregacion': 'mes'}


# ---------------------------------------------------------------- búsqueda

def buscar(texto):
    res = {'bcra': [], 'datos_gob_ar': []}
    try:
        d = json.loads(http(BCRA_API + '?limit=3000'))
        palabras = [p for p in texto.lower().split() if p]
        for x in d.get('results', []):
            s = (x.get('descripcion') or '').lower()
            if all(p in s for p in palabras):
                res['bcra'].append({'id': x['idVariable'], 'desc': x['descripcion'].strip(),
                                    'categoria': x.get('categoria'), 'moneda': x.get('moneda'),
                                    'unidad': x.get('unidadExpresion'),
                                    'periodicidad': x.get('periodicidad'),
                                    'desde': x.get('primerFechaInformada'),
                                    'hasta': x.get('ultFechaInformada')})
    except Exception as e:  # noqa: BLE001
        res['bcra_error'] = str(e)
    try:
        q = urllib.parse.urlencode({'q': texto, 'limit': 15})
        d = json.loads(http(DATOS_BUSCAR + '?' + q))
        for x in d.get('data', []):
            f = x['field']
            res['datos_gob_ar'].append({'id': f['id'], 'desc': f.get('description'),
                                        'unidad': f.get('units'), 'frecuencia': f.get('frequency'),
                                        'desde': f.get('time_index_start'),
                                        'hasta': f.get('time_index_end')})
    except Exception as e:  # noqa: BLE001
        res['datos_error'] = str(e)
    res['bcra'] = res['bcra'][:40]
    res['nota'] = ('Usar --bcra-id ID (diaria: se toma fin de mes; agregar --promediar si es tasa '
                   'o tipo de cambio) o --datos-id ID. Revisar moneda (ML pesos, ME dólares) y unidad.')
    return res


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--series', nargs='+', help='alias del catálogo (por defecto, un set amplio)')
    ap.add_argument('--desde', default='2019-01', help='YYYY-MM (por defecto 2019-01)')
    ap.add_argument('--hasta', help='YYYY-MM (por defecto, último disponible)')
    ap.add_argument('--salida', help='CSV de salida (por defecto macro.csv)')
    ap.add_argument('--bcra-id', nargs='*', type=int, default=[], help='ids extra de la API del BCRA')
    ap.add_argument('--datos-id', nargs='*', default=[], help='ids extra de datos.gob.ar')
    ap.add_argument('--promediar', action='store_true', help='promediar en el mes las --bcra-id diarias')
    ap.add_argument('--catalogo', action='store_true')
    ap.add_argument('--buscar')
    a = ap.parse_args()

    if a.catalogo:
        cat = {k: {'desc': v[2], 'unidad': v[3], 'fuente': v[0]} for k, v in CATALOGO.items()}
        cat.update({k: {'desc': v[1], 'unidad': v[2], 'fuente': 'CALCULADO', 'insumos': v[0]}
                    for k, v in DERIVADAS.items()})
        cm.salida({'catalogo': cat, 'por_defecto': POR_DEFECTO})
    if a.buscar:
        cm.salida(buscar(a.buscar))

    pedidas = a.series or POR_DEFECTO
    desconocidas = [k for k in pedidas if k not in CATALOGO and k not in DERIVADAS]
    if desconocidas:
        cm.salida({'error': 'Alias desconocidos: %s' % desconocidas,
                   'ayuda': 'Ver --catalogo o usar --bcra-id / --datos-id'}, 2)
    base = [k for k in pedidas if k in CATALOGO]
    der = [k for k in pedidas if k in DERIVADAS]
    for k in der:
        for ins in DERIVADAS[k][0]:
            if ins not in base:
                base.append(ins)

    # Pedir un año extra para poder calcular variaciones interanuales
    desde_q = cm.mes_anterior(a.desde, 13)
    tareas = []
    for k in base:
        fuente, idv, desc, unidad, agr = CATALOGO[k]
        tareas.append((k, fuente, idv, desc, unidad, agr))
    for idv in a.bcra_id:
        tareas.append(('bcra_%d' % idv, 'bcra', idv, 'BCRA serie %d' % idv, '', 'prom' if a.promediar else 'fin'))
    datos_extra = []
    for idv in a.datos_id:
        datos_extra.append(('datos_' + idv, 'datos', idv, 'datos.gob.ar %s' % idv, '', 'mes'))
    tareas += datos_extra

    series, meta, errores = {}, {}, {}

    def traer_bcra(t):
        k, _, idv, _, _, agr = t
        return k, a_mensual(serie_bcra(idv, desde_q), agr)

    try:
        with cf.ThreadPoolExecutor(8) as ex:
            futs = {}
            for t in tareas:
                if t[1] == 'bcra':
                    futs[ex.submit(traer_bcra, t)] = t
            # Una consulta por serie: si se mezclan frecuencias, la API lleva todo a la menor
            ids_datos = [t for t in tareas if t[1] == 'datos']
            fut_datos = {ex.submit(serie_datos, [t[2]], desde_q[:7]): t for t in ids_datos}
            fut_ipc = ex.submit(serie_indec_ipc) if any(t[1] == 'indec' for t in tareas) else None
            for f in cf.as_completed(futs):
                t = futs[f]
                try:
                    k, s = f.result()
                    series[k] = s
                except SinRed:
                    raise
                except Exception as e:  # noqa: BLE001
                    errores[t[0]] = str(e)
            for f in cf.as_completed(fut_datos):
                t = fut_datos[f]
                try:
                    s = {d[:7]: v for d, v in f.result().get(t[2], {}).items()}
                    if t[0] == 'desocupacion' and s and max(s.values()) < 1:
                        s = {m: 100 * v for m, v in s.items()}  # viene como fracción
                    # Las trimestrales vienen fechadas al inicio del trimestre:
                    # se fechan al último mes (cuando termina el período medido).
                    if t[0] in ('desocupacion', 'pbi_real'):
                        s = {cm.mes_anterior(m, -2): v for m, v in s.items()}
                    series[t[0]] = s
                except SinRed:
                    raise
                except Exception as e:  # noqa: BLE001
                    errores[t[0]] = str(e)
            if fut_ipc:
                try:
                    ipc = fut_ipc.result()
                    if 'ipc' in base:
                        series['ipc'] = ipc['Nivel general']
                    if 'ipc_nucleo' in base:
                        series['ipc_nucleo'] = ipc['Núcleo']
                except SinRed:
                    raise
                except Exception as e:  # noqa: BLE001
                    errores['ipc'] = str(e)
    except SinRed as e:
        cm.salida({'error': 'Sin acceso de red a las fuentes: %s' % e, 'sin_acceso_red': True,
                   'ayuda': 'Habilitar api.bcra.gob.ar, apis.datos.gob.ar y www.indec.gob.ar'}, 2)

    # IPC antes de dic-2016: empalmar hacia atrás con el CER (aproximación)
    if 'ipc' in series and series['ipc'] and min(series['ipc']) > desde_q:
        try:
            cer = a_mensual(serie_bcra(30, desde_q), 'fin')
            primero = min(series['ipc'])
            if primero in cer:
                f = series['ipc'][primero] / cer[primero]
                for m, v in cer.items():
                    if m < primero:
                        series['ipc'][m] = v * f
                meta['_aviso_ipc'] = ('IPC INDEC disponible desde %s; los meses anteriores se '
                                      'empalmaron con el CER (aproximación).' % primero)
        except Exception as e:  # noqa: BLE001
            errores['empalme_ipc_cer'] = str(e)

    tabla = {}
    for k, s in series.items():
        for m, v in s.items():
            tabla.setdefault(m, {})[k] = v
    for t in tareas:
        k, fuente, idv, desc, unidad, agr = t
        meta[k] = {'desc': desc, 'unidad': unidad, 'agregacion': agr,
                   'fuente': {'bcra': 'BCRA API Estadísticas v4 (id %s)' % idv,
                              'datos': 'datos.gob.ar Series de Tiempo (%s)' % idv,
                              'indec': 'INDEC IPC Nacional (serie_ipc_divisiones.csv)'}[fuente]}
    calcular_derivadas(tabla, der, meta)

    # CER y UVA se publican por adelantado: no pasar del mes en curso
    hasta = a.hasta or time.strftime('%Y-%m')
    meses = [m for m in sorted(tabla) if a.desde <= m <= hasta]
    columnas = [k for k in pedidas] + [t[0] for t in tareas if t[0] not in pedidas]
    columnas = [c for c in dict.fromkeys(columnas) if any(tabla[m].get(c) is not None for m in meses)]

    ruta = a.salida or 'macro.csv'
    with open(ruta, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['periodo'] + columnas)
        for m in meses:
            w.writerow([m] + ['' if tabla[m].get(c) is None else round(tabla[m][c], 6) for c in columnas])

    resumen = {}
    for c in columnas:
        con = [m for m in meses if tabla[m].get(c) is not None]
        info = dict(meta.get(c, {}))
        if con:
            info.update({'desde': con[0], 'hasta': con[-1], 'ultimo': round(tabla[con[-1]][c], 4)})
        resumen[c] = info
    out = {'archivo': os.path.abspath(ruta), 'meses': len(meses), 'desde': meses[0] if meses else None,
           'hasta': meses[-1] if meses else None, 'series': resumen}
    if '_aviso_ipc' in meta:
        out['aviso'] = meta['_aviso_ipc']
    if errores:
        out['errores_fuente'] = errores
    out['nota'] = ('Stocks en pesos corrientes: deflactar con ipc antes de comparar en el tiempo. '
                   'Trimestrales (desocupacion, pbi_real) solo en el último mes de cada trimestre.')
    cm.salida(out)


if __name__ == '__main__':
    main()
