#!/usr/bin/env python3
"""
Motor de análisis del Estratega Bancario. Trabaja sobre el panel de
panel.py (bcra-oraculo) y las series de macro_ar.py.

Subcomandos (cada uno imprime un JSON, guarda un CSV con el detalle y, salvo
`preparar` y `calidad`, un gráfico PNG):

  proforma      suma hacia atrás entidades absorbidas (fusiones) al absorbente
  preparar      panel nominal -> panel analítico: pesos constantes, ratios de
                modelo de negocio, cuotas de mercado y crecimiento real
  calidad       saltos imposibles, picos aislados (errores de carga) y saltos
                persistentes (posibles fusiones); --limpiar escribe un panel corregido
  cuotas        cuota de mercado, cambio en pp, ranking, HHI y descomposición del
                crecimiento en efecto mercado × efecto cuota; con varios --campo, mapa
                de cuotas por producto
  rentabilidad  árbol del ROA (margen, comisiones, incobrabilidad, gastos, resultado
                monetario, impuesto) del foco vs pares y por segmento
  brechas       banco foco vs pares: percentil, brecha a la mediana y tamaño en
                pesos de cerrarla (mix, penetración y "fair share")
  correlacion   temporal (variaciones, con rezagos y n efectivo) o transversal
                (entre bancos, Spearman)
  segmentar     clusters de modelo de negocio (k-means + Ward, silhouette,
                estabilidad) y desempeño por segmento
  sensibilidad  elasticidad de una métrica bancaria a variables macro: OLS con
                errores HAC por banco y panel con efectos fijos
  anomalias     cambios recientes fuera de lo normal vs historia propia y vs pares
  novedades     lo más importante del mes, automático (con las alertas de cartera de
                riesgo-bancario si está instalado)
  grafico       linea | dispersion | barras | macro (exploratorios)

Uso típico:
    python3 analizar.py preparar --panel panel.csv --macro macro.csv --salida analitico.csv
    python3 analizar.py calidad --datos analitico.csv
    python3 analizar.py cuotas --datos analitico.csv --campo bPers --desde 2024-07
    python3 analizar.py brechas --datos analitico.csv --foco Galicia --pares top10
    python3 analizar.py correlacion --datos analitico.csv --macro macro.csv --entidad sistema \\
        --variables irr_cons bPers_ia --macro-vars salario_real tasa_real_personales desocupacion
    python3 analizar.py correlacion --datos analitico.csv --modo transversal --variables mix_pers irr_cons roe
    python3 analizar.py segmentar --datos analitico.csv --foco Macro
    python3 analizar.py sensibilidad --datos analitico.csv --macro macro.csv --y irr_cons \\
        --x salario_real tasa_real_personales --rezago 3 --foco Galicia
    python3 analizar.py anomalias --datos analitico.csv --campos irr_cons cuota_bPers mix_pers
    python3 analizar.py grafico linea --datos analitico.csv --campo cuota_bPers --entidades Galicia Santander BBVA
"""
import argparse
import json
import math
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as cm  # noqa: E402

cm.exigir_librerias()
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

import graficos as gr  # noqa: E402

warnings.filterwarnings('ignore')
bc = cm.importar_bcra()

GRUPOS = {'SISTEMA': 'AAA00', 'PUBLICOS': 'AAA10', 'PRIVADOS': 'AAA20', 'COMPANIAS': 'AAA30',
          'TOP10': 'AAA50'}
FLUJOS = ['bRes', 'bIF', 'bEgF', 'bInc', 'bIS', 'bES', 'bGA', 'bRM', 'bIG']
CANTIDADES = ['cc', 'cah', 'cah_social', 'cprev', 'pla', 'tit', 'deb', 'emp', 'pf_ind', 'pf_emp',
              'op_hip', 'op_prend', 'remu', 'remu_emp']
TRIMESTRALES = ['cc', 'cah', 'cah_social', 'cprev', 'pla', 'tit', 'deb', 'emp', 'pf_ind', 'pf_emp',
                'op_hip', 'op_prend', 'op_otros']
CUOTAS = ['bA', 'bPr_priv', 'bDe_priv', 'bPers', 'bHip', 'bPrend', 'bDoc', 'bAdel', 'bCA', 'bPF',
          'bCC', 'bPN', 'bIS', 'tf_total', 'con_total', 'com_total', 'pla', 'tit', 'deb', 'cah',
          'cc', 'cprev', 'remu', 'remu_emp', 'emp']
CRECIMIENTO = ['bA', 'bPr_priv', 'bDe_priv', 'bPers', 'bHip', 'bPrend', 'bDoc', 'bAdel', 'bCA',
               'bPF', 'bCC', 'bPN', 'tf_total', 'con_total', 'com_total']

DERIVADOS = {
    'ld_ratio': ('Préstamos privados / depósitos privados', '%'),
    'prest_activo': ('Préstamos / activo', '%'),
    'titulos_activo': ('Títulos públicos y privados / activo', '%'),
    'liquidez_activo': ('Efectivo y depósitos en bancos / activo', '%'),
    'pn_activo': ('Patrimonio neto / activo', '%'),
    'mix_pers': ('Personales / préstamos privados', '%'),
    'mix_hip': ('Hipotecarios / préstamos privados', '%'),
    'mix_prend': ('Prendarios / préstamos privados', '%'),
    'mix_doc': ('Documentos / préstamos privados', '%'),
    'mix_adel': ('Adelantos / préstamos privados', '%'),
    'mix_otros': ('Resto (tarjetas y otros) / préstamos privados', '%'),
    'mix_cc': ('Cuenta corriente / depósitos privados', '%'),
    'mix_ca': ('Caja de ahorros / depósitos privados', '%'),
    'mix_pf': ('Plazo fijo / depósitos privados', '%'),
    'spread': ('Tasa implícita de préstamos − tasa implícita de depósitos', 'pp'),
    'costo_riesgo': ('Cargo por incobrabilidad anualizado / préstamos privados', '%'),
    'eficiencia': ('Gastos de administración / (margen financiero + margen por servicios)', '%'),
    'fee_ratio': ('Margen por servicios / (margen financiero + margen por servicios)', '%'),
    'pla_por_tit': ('Tarjetas de crédito por titular', 'veces'),
    'deb_por_cah': ('Tarjetas de débito por caja de ahorro', 'veces'),
    'saldo_ca_prom': ('Saldo promedio por caja de ahorro', 'pesos'),
    'pers_por_remu': ('Préstamos personales por cuenta sueldo', 'pesos'),
    'log_activo': ('Logaritmo del activo (tamaño)', 'log'),
    'irr_cons_sin_dilucion': ('Mora de consumo sobre la cartera de consumo de 12 meses antes', '%'),
    'irr_tot_sin_dilucion': ('Mora total sobre las financiaciones de 12 meses antes', '%'),
}
CORTAS = {
    'mix_pers': 'Mix personales', 'mix_hip': 'Mix hipotecarios', 'mix_prend': 'Mix prendarios',
    'mix_doc': 'Mix documentos', 'mix_adel': 'Mix adelantos', 'mix_otros': 'Mix tarjetas y otros',
    'mix_cc': 'Depósitos en cta. cte.', 'mix_ca': 'Depósitos en caja de ahorro',
    'mix_pf': 'Depósitos a plazo', 'ld_ratio': 'Préstamos / depósitos',
    'prest_activo': 'Préstamos / activo', 'titulos_activo': 'Títulos / activo',
    'liquidez_activo': 'Liquidez / activo', 'pn_activo': 'Patrimonio / activo',
    'spread': 'Spread de tasas', 'tasa_prest': 'Tasa implícita préstamos',
    'tasa_dep': 'Tasa implícita depósitos', 'irr_tot': 'Mora total', 'irr_cons': 'Mora consumo',
    'irr_com': 'Mora comercial', 'irr_priv': 'Mora sector privado', 'prev_irr': 'Cobertura con previsiones',
    'costo_riesgo': 'Costo de riesgo', 'roe': 'ROE', 'roa': 'ROA', 'eficiencia': 'Gastos / ingresos',
    'absorc_gastos': 'Gastos / volumen de negocio', 'fee_ratio': 'Peso de comisiones en ingresos',
    'result_serv_activo': 'Comisiones netas / activo', 'pla_por_tit': 'Tarjetas por titular',
    'saldo_ca_prom': 'Saldo prom. caja de ahorro', 'pers_por_remu': 'Personales por cuenta sueldo',
    'dep_empleado': 'Depósitos por empleado', 'fin_empleado': 'Financiaciones por empleado',
    'deb_por_cah': 'Débito por caja de ahorro', 'log_activo': 'Tamaño (log activo)',
    'margen_fin_activo': 'Margen financiero / activo', 'apalancamiento': 'Apalancamiento',
}


PRODUCTOS = {'bA': 'Activo', 'bPr_priv': 'Préstamos privados', 'bPers': 'Personales', 'bHip': 'Hipotecarios',
             'bPrend': 'Prendarios', 'bDoc': 'Documentos', 'bAdel': 'Adelantos', 'bDe_priv': 'Depósitos privados',
             'bCA': 'Caja de ahorros ($)', 'bPF': 'Plazo fijo ($)', 'bCC': 'Cuenta corriente ($)',
             'bPN': 'Patrimonio', 'bIS': 'Comisiones', 'tf_total': 'Financiaciones', 'con_total': 'Cartera consumo',
             'com_total': 'Cartera comercial', 'remu': 'Cuentas sueldo', 'remu_emp': 'Empresas pagadoras',
             'pla': 'Tarjetas crédito', 'tit': 'Titulares tarjeta', 'deb': 'Tarjetas débito',
             'cah': 'Cajas de ahorro (#)', 'cc': 'Cuentas corrientes (#)', 'cprev': 'Cuentas previsionales',
             'emp': 'Empleados'}


def corta(m):
    b = m.split(':')[0]
    if b in CORTAS:
        return CORTAS[b]
    if b.startswith('cuota_'):
        return 'Cuota ' + PRODUCTOS.get(b[6:], b[6:]).lower()
    if b.endswith('_ia'):
        return 'Crec. real ' + b[:-3]
    return b


# Dirección "mejor" para marcar fortalezas/debilidades (None = elección estratégica)
MEJOR = {'roe': True, 'roa': True, 'roe_ord': True, 'irr_tot': False, 'irr_cons': False,
         'irr_com': False, 'irr_priv': False, 'prev_irr': True, 'costo_riesgo': False,
         'eficiencia': False, 'absorc_gastos': False, 'fee_ratio': True, 'spread': True,
         'tasa_dep': False, 'dep_empleado': True, 'fin_empleado': True, 'pla_por_tit': True,
         'deb_por_cah': True, 'saldo_ca_prom': True, 'pers_por_remu': True, 'roa_adm': False,
         'margen_fin_activo': True, 'result_serv_activo': True, 'pn_activo': True,
         'margen_rent_gastos': True}
BRECHAS_DEFECTO = ['mix_pers', 'mix_hip', 'mix_prend', 'mix_doc', 'mix_adel', 'mix_otros',
                   'mix_ca', 'mix_pf', 'ld_ratio', 'titulos_activo', 'spread', 'tasa_prest',
                   'tasa_dep', 'irr_tot', 'irr_cons', 'irr_com', 'prev_irr', 'costo_riesgo',
                   'roe', 'roa', 'eficiencia', 'absorc_gastos', 'fee_ratio', 'result_serv_activo',
                   'pla_por_tit', 'saldo_ca_prom', 'pers_por_remu', 'dep_empleado', 'fin_empleado']
SEG_DEFECTO = ['mix_pers', 'mix_hip', 'mix_prend', 'mix_doc', 'mix_adel', 'mix_otros', 'mix_cc',
               'mix_ca', 'mix_pf', 'prest_activo', 'titulos_activo', 'ld_ratio', 'log_activo']
SEG_RESULTADOS = ['roe', 'roa', 'irr_tot', 'irr_cons', 'spread', 'tasa_prest', 'tasa_dep',
                  'absorc_gastos', 'costo_riesgo', 'fee_ratio']
# (base, objetivo, lectura)
FAIR_SHARE = [
    ('remu', 'bPers', 'convertir su cuota de cuentas sueldo en cuota de préstamos personales'),
    ('remu', 'pla', 'convertir su cuota de cuentas sueldo en cuota de tarjetas de crédito'),
    ('remu', 'bCA', 'retener en caja de ahorros su cuota de cuentas sueldo'),
    ('cprev', 'bPers', 'prestarle a su base de jubilados (cuentas previsionales) en proporción a su cuota'),
    ('bDe_priv', 'bPr_priv', 'prestar en proporción a su cuota de depósitos privados'),
    ('cah', 'pla', 'llevar a su base de cajas de ahorro la misma cuota en tarjetas'),
    ('bA', 'bIS', 'cobrar comisiones en proporción a su tamaño'),
]


# =========================================================== utilidades

def unidad(campo):
    base = campo.split(':')[0]
    if base.startswith('cuota_'):
        return '%'
    if base.endswith('_ia'):
        return '%'
    if base in DERIVADOS:
        return DERIVADOS[base][1]
    if base in bc.CAMPOS:
        return bc.describir(base)['unidad']
    try:
        import macro_ar
        if base in macro_ar.CATALOGO:
            return macro_ar.CATALOGO[base][3]
        if base in macro_ar.DERIVADAS:
            return macro_ar.DERIVADAS[base][2]
    except Exception:  # noqa: BLE001
        pass
    return ''


def descripcion(campo):
    base = campo.split(':')[0]
    if base.startswith('cuota_'):
        return 'Cuota de mercado de %s (%% del sistema)' % descripcion(base[6:])
    if base.endswith('_ia') and base[:-3] in bc.CAMPOS:
        return 'Crecimiento real interanual de %s' % descripcion(base[:-3])
    if base in DERIVADOS:
        return DERIVADOS[base][0]
    if base in bc.CAMPOS:
        return bc.describir(base)['desc']
    try:
        import macro_ar
        if base in macro_ar.CATALOGO:
            return macro_ar.CATALOGO[base][2]
        if base in macro_ar.DERIVADAS:
            return macro_ar.DERIVADAS[base][1]
    except Exception:  # noqa: BLE001
        pass
    return base


def es_tasa(campo):
    u = unidad(campo)
    return u in ('%', '% TNA', 'pp', 'veces', 'log') or campo.split(':')[0].endswith('_ia')


def cargar(ruta):
    df = pd.read_csv(ruta, dtype={'codigo': str, 'periodo': str, 'entidad': str, 'tipo': str})
    df['tipo'] = df['tipo'].fillna('')
    return df


def meta_de(ruta):
    p = os.path.splitext(ruta)[0] + '.meta.json'
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}


def fuente_txt(meta, extra=''):
    s = 'Fuente: BCRA (Información de Entidades Financieras)'
    if meta.get('base'):
        s += ', INDEC. Montos en pesos constantes de %s' % meta['base']
    return s + ('. ' + extra if extra else '.')


def resolver(df, q):
    """Código de una entidad o grupo a partir de nombre, alias o código."""
    q0 = str(q).strip()
    ents = df[['codigo', 'entidad']].drop_duplicates('codigo')
    n = bc.norm(q0)
    if n in GRUPOS or n in bc.ALIAS_GRUPO:
        g = GRUPOS.get(n) or bc.GRUPOS[bc.ALIAS_GRUPO[n]][0]
        return g
    if q0 in set(ents['codigo']):
        return q0
    n_sin = n[6:] if n.startswith('BANCO ') else n
    for k in (n, n_sin):
        if k in bc.ALIAS and str(bc.ALIAS[k]) in set(ents['codigo']):
            return str(bc.ALIAS[k])
    tokens = [t for t in n.split() if t not in bc.VACIAS] or n.split()
    cands = [r.codigo for r in ents.itertuples()
             if all(any(w == t or (len(t) >= 4 and w.startswith(t)) for w in bc.norm(r.entidad).split())
                    for t in tokens)]
    if len(cands) == 1:
        return cands[0]
    if cands:
        cm.salida({'error': '"%s" coincide con varias entidades' % q0,
                   'candidatos': {c: ents.set_index('codigo').loc[c, 'entidad'] for c in cands}}, 2)
    cm.salida({'error': '"%s" no está en el panel' % q0,
               'ayuda': 'Ver lista_entidades del JSON de panel.py o ampliar --entidades'}, 2)


def nombre(df, cod):
    s = df.loc[df['codigo'] == cod, 'entidad']
    return s.iloc[0] if len(s) else cod


def ultimo_con_dato(df, campo, hasta=None):
    d = df[df[campo].notna() & (df['tipo'] != 'grupo')] if campo in df else df.iloc[0:0]
    if hasta:
        d = d[d['periodo'] <= hasta]
    return d['periodo'].max() if len(d) else None


def periodo_cercano(df, campo, objetivo):
    """Último período <= objetivo con dato en el campo (para trimestrales)."""
    return ultimo_con_dato(df, campo, objetivo)


def universo(df, cual, fecha, excluir=()):
    """Códigos de entidades (no grupos) según 'bancos', 'privados', 'publicos', 'companias',
    'todas', 'topN' (N mayores bancos por activo a la fecha) o lista de nombres."""
    ent = df[(df['tipo'] != 'grupo')]
    cual = cual if isinstance(cual, list) else [cual]
    if len(cual) == 1 and isinstance(cual[0], str):
        c = cual[0].lower()
        tipos = {'bancos': ('publico', 'privado'), 'privados': ('privado',),
                 'publicos': ('publico',), 'companias': ('compania',),
                 'todas': ('publico', 'privado', 'compania')}
        if c in tipos:
            cods = sorted(ent.loc[ent['tipo'].isin(tipos[c]), 'codigo'].unique())
            return [x for x in cods if x not in excluir]
        if c.startswith('top') and c[3:].isdigit():
            n = int(c[3:])
            f = ent[(ent['periodo'] == fecha) & ent['tipo'].isin(('publico', 'privado'))]
            f = f[~f['codigo'].isin(excluir)].sort_values('bA', ascending=False)
            return list(f['codigo'].head(n))
    return [x for x in (resolver(df, q) for q in cual) if x not in excluir]


def a_mensual(s):
    """Serie indexada por 'YYYY-MM' -> reindexada a todos los meses del rango."""
    s = s.dropna()
    if s.empty:
        return s
    idx = cm.meses_entre(s.index.min(), s.index.max())
    return s.reindex(idx)


def excluir(s, rangos):
    """Pone en NaN los meses dentro de rangos 'YYYY-MM:YYYY-MM'.

    Se aplica a los niveles ANTES de transformar: así una variación de 12 meses que compara contra
    un mes excluido también queda afuera (si no, los meses siguientes al período excluido seguían
    arrastrando sus niveles distorsionados)."""
    if not rangos:
        return s
    s = s.copy()
    for r in rangos:
        lo, hi = (r.split(':') + [r])[:2]
        s[(s.index >= lo) & (s.index <= hi)] = np.nan
    return s


def transformar(s, campo, modo):
    """Variación para análisis temporal. modo: auto|ia|dif|var|mensual|nivel.

    auto/ia: 12 meses (diferencia en pp si es tasa o %, variación % si es nivel)."""
    if ':' in campo:
        modo = campo.split(':')[1]
    if modo == 'nivel':
        return s
    tasa = es_tasa(campo)
    k = 1 if modo == 'mensual' else 12
    if modo == 'dif' or (modo in ('auto', 'ia', 'mensual') and tasa):
        return s - s.shift(k)
    return 100 * (s / s.shift(k) - 1)


def etiqueta_tr(campo, modo):
    if ':' in campo:
        modo = campo.split(':')[1]
    if modo == 'nivel':
        return 'nivel'
    if modo == 'mensual':
        return 'dif. mensual (pp)' if es_tasa(campo) else 'var. mensual (%)'
    return 'dif. 12m (pp)' if (modo == 'dif' or es_tasa(campo)) else 'var. 12m (%)'


def bh(pvals):
    """q-valores de Benjamini-Hochberg."""
    p = np.asarray(pvals, dtype=float)
    n = np.sum(~np.isnan(p))
    q = np.full_like(p, np.nan)
    if n == 0:
        return q
    orden = np.argsort(np.where(np.isnan(p), np.inf, p))
    ranks = np.empty_like(orden)
    ranks[orden] = np.arange(1, len(p) + 1)
    raw = p * n / ranks
    sorted_raw = raw[orden]
    acum = np.minimum.accumulate(sorted_raw[::-1])[::-1]
    q[orden] = np.minimum(acum, 1)
    q[np.isnan(p)] = np.nan
    return q


def r1(x):
    x = pd.Series(x).dropna()
    if len(x) < 4:
        return 0.0
    v = x.autocorr(1)
    return 0.0 if v is None or np.isnan(v) else float(v)


def corr_neff(x, y):
    """Pearson con n efectivo corregido por autocorrelación (Bartlett)."""
    d = pd.concat([x, y], axis=1).dropna()
    n = len(d)
    if n < 8 or d.iloc[:, 0].std() == 0 or d.iloc[:, 1].std() == 0:
        return None
    r = float(np.corrcoef(d.iloc[:, 0], d.iloc[:, 1])[0, 1])
    a, b = r1(d.iloc[:, 0]), r1(d.iloc[:, 1])
    neff = n * (1 - a * b) / (1 + a * b) if (1 + a * b) else n
    neff = float(min(n, max(4, neff)))
    t = r * math.sqrt(max(neff - 2, 1) / max(1e-12, 1 - r * r))
    p = float(2 * stats.t.sf(abs(t), max(neff - 2, 1)))
    rho = float(stats.spearmanr(d.iloc[:, 0], d.iloc[:, 1])[0])
    return {'r': r, 'rho': rho, 'n': n, 'n_ef': round(neff, 1), 'p': p}


def redondear(obj, dec=4):
    if isinstance(obj, float):
        return None if np.isnan(obj) else round(obj, dec)
    if isinstance(obj, dict):
        return {k: redondear(v, dec) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redondear(v, dec) for v in obj]
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else round(float(obj), dec)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


def ruta_salida(a, nombre_archivo):
    d = a.salida_dir or '.'
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, nombre_archivo)


def serie(df, cod, campo):
    d = df[df['codigo'] == cod].set_index('periodo')
    if campo not in d:
        cm.salida({'error': 'El campo %s no está en los datos' % campo,
                   'ayuda': 'Correr "preparar" o revisar el nombre (ver JSON de preparar)'}, 2)
    return pd.to_numeric(d[campo], errors='coerce').sort_index()


def exigir_campos(df, campos):
    faltan = [c.split(':')[0] for c in campos if c.split(':')[0] not in df.columns]
    if faltan:
        cm.salida({'error': 'Campos que no están en los datos: %s' % faltan,
                   'ayuda': 'Los derivados (mix_*, cuota_*, *_ia, eficiencia, etc.) se crean con '
                            '"preparar"; los del BCRA hay que pedirlos en panel.py --campos (ver references/diccionario.md de bcra-oraculo)'}, 2)


# =========================================================== preparar

def cmd_preparar(a):
    df = cargar(a.panel)
    num = [c for c in df.columns if c not in ('periodo', 'codigo', 'entidad', 'tipo')]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    avisos = []

    def div(x, y, k=100.0):
        if x not in df or y not in df:
            return pd.Series(np.nan, index=df.index)
        den = df[y].where(df[y] != 0)
        return k * df[x] / den

    # Ratios (invariantes a la inflación: se calculan sobre nominales)
    df['ld_ratio'] = div('bPr_priv', 'bDe_priv')
    df['prest_activo'] = div('bPr', 'bA')
    df['titulos_activo'] = div('bTi', 'bA')
    df['liquidez_activo'] = div('bEf', 'bA')
    df['pn_activo'] = div('bPN', 'bA')
    # Un producto vacío ('---') en un banco que sí informa su cartera total es un producto que no
    # tiene: cuenta como 0 % del mix, para no sacar a ese banco de la mediana de sus pares.
    def parte(c, total):
        return df[c].where(df[c].notna() | df[total].isna(), 0.0) if total in df else df[c]

    for k, c in (('mix_pers', 'bPers'), ('mix_hip', 'bHip'), ('mix_prend', 'bPrend'),
                 ('mix_doc', 'bDoc'), ('mix_adel', 'bAdel')):
        if c in df and 'bPr_priv' in df:
            df[k] = 100 * parte(c, 'bPr_priv') / df['bPr_priv'].where(df['bPr_priv'] != 0)
    partes = [c for c in ('bPers', 'bHip', 'bPrend', 'bDoc', 'bAdel') if c in df]
    if 'bPr_priv' in df and partes:
        resto = df['bPr_priv'] - df[partes].fillna(0).sum(axis=1)
        df['mix_otros'] = 100 * resto.clip(lower=0) / df['bPr_priv'].where(df['bPr_priv'] != 0)
    for k, c in (('mix_cc', 'bCC'), ('mix_ca', 'bCA'), ('mix_pf', 'bPF')):
        if c in df and 'bDe_priv' in df:
            df[k] = 100 * parte(c, 'bDe_priv') / df['bDe_priv'].where(df['bDe_priv'] != 0)
    if 'tasa_prest' in df and 'tasa_dep' in df:
        df['spread'] = df['tasa_prest'] - df['tasa_dep']
    mes = df['periodo'].str[5:7].astype(int)
    if 'bInc' in df and 'bPr_priv' in df:
        df['costo_riesgo'] = -100 * df['bInc'] * 12 / mes / df['bPr_priv'].where(df['bPr_priv'] > 0)
    ing = [c for c in ('bIF', 'bEgF', 'bIS', 'bES') if c in df]
    if len(ing) == 4:
        tot = df[ing].sum(axis=1, min_count=4)
        tot = tot.where(tot > 0)
        if 'bGA' in df:
            df['eficiencia'] = -100 * df['bGA'] / tot
        df['fee_ratio'] = 100 * (df['bIS'] + df['bES']) / tot
    df['pla_por_tit'] = div('pla', 'tit', 1.0)
    df['deb_por_cah'] = div('deb', 'cah', 1.0)

    # Pesos constantes
    meta = {'panel': os.path.abspath(a.panel), 'deflactado': False}
    monetarios = [c for c in num if bc.CAMPOS.get(c, (None, None, None))[2] == 'millones de pesos']
    if a.macro:
        mac = pd.read_csv(a.macro, dtype={'periodo': str}).set_index('periodo')
        if 'ipc' not in mac:
            cm.salida({'error': 'El CSV macro no tiene la columna ipc'}, 2)
        ipc = mac['ipc'].dropna()
        base = a.base or df.loc[df['tipo'] != 'grupo', 'periodo'].max()
        if base not in ipc.index:
            base = ipc.index.max()
            avisos.append('Sin IPC para la base pedida: se usó %s' % base)
        f = df['periodo'].map(lambda p: ipc.get(base) / ipc.get(p) if p in ipc.index else np.nan)
        sin_ipc = sorted(df.loc[f.isna(), 'periodo'].unique())
        if sin_ipc:
            avisos.append('Meses sin IPC (quedan sin deflactar, en NaN): %s' % sin_ipc)
        for c in monetarios:
            df[c] = df[c] * f
        meta.update({'deflactado': True, 'base': base, 'deflactor': 'IPC Nacional INDEC',
                     'campos_deflactados': monetarios})
        if any(c in df for c in FLUJOS):
            avisos.append('Resultados acumulados del ejercicio deflactados con el IPC de cada cierre '
                          '(aproximación: bajo NIC 29 ya están en moneda de ese cierre).')
    else:
        avisos.append('Sin --macro: los montos quedan en pesos corrientes (no comparar en el tiempo).')

    # Mora "sin dilución": cartera irregular de hoy sobre la cartera de hace 12 meses (montos reales).
    # Un banco que crece rápido diluye su mora; este ratio lo corrige.
    clave0 = df.set_index(['codigo', 'periodo'])
    for k, base in (('irr_cons', 'con_total'), ('irr_tot', 'tf_total')):
        if k in df and base in df:
            prev = pd.Series([clave0[base].get((c, cm.mes_anterior(p, 12)), np.nan)
                              for c, p in zip(df['codigo'], df['periodo'])], index=df.index)
            df[k + '_sin_dilucion'] = df[k] * df[base] / prev.where(prev > 0)
    df['saldo_ca_prom'] = div('bCA', 'cah', 1e6)
    df['pers_por_remu'] = div('bPers', 'remu', 1e6)
    if 'bA' in df:
        df['log_activo'] = np.log(df['bA'].where(df['bA'] > 0))

    # Cuotas de mercado sobre el total del sistema (agregado oficial AAA00)
    sis = df[df['codigo'] == 'AAA00'].set_index('periodo')
    if sis.empty:
        avisos.append('No está el agregado del sistema (AAA00): no se calcularon cuotas.')
    for c in CUOTAS:
        if c in df and not sis.empty:
            tot = df['periodo'].map(sis[c])
            df['cuota_' + c] = 100 * df[c] / tot.where(tot > 0)

    # Crecimiento real interanual
    clave = df.set_index(['codigo', 'periodo'])
    for c in CRECIMIENTO:
        if c not in df:
            continue
        previo = [clave[c].get((cod, cm.mes_anterior(p, 12)), np.nan)
                  for cod, p in zip(df['codigo'], df['periodo'])]
        prev = pd.Series(previo, index=df.index)
        df[c + '_ia'] = 100 * (df[c] / prev.where(prev > 0) - 1)

    df.to_csv(a.salida, index=False)
    nuevas = [c for c in df.columns if c not in num and c not in ('periodo', 'codigo', 'entidad', 'tipo')]
    meta['columnas_nuevas'] = {c: '%s [%s]' % (descripcion(c), unidad(c)) for c in nuevas}
    with open(os.path.splitext(a.salida)[0] + '.meta.json', 'w') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    out = {'archivo': os.path.abspath(a.salida), 'filas': len(df),
           'entidades': int(df.loc[df['tipo'] != 'grupo', 'codigo'].nunique()),
           'desde': df['periodo'].min(), 'hasta': df['periodo'].max(),
           'pesos_constantes_de': meta.get('base'), 'columnas_nuevas': meta['columnas_nuevas'],
           'notas': ['costo_riesgo anualiza el cargo acumulado del ejercicio (supone cierre en diciembre).',
                     'mix_otros incluye tarjetas de crédito (el balance no las abre).',
                     'Cuotas sobre el total del sistema (bancos + compañías financieras).',
                     'Campos trimestrales (pla, tit, cah, ...) solo tienen dato a fin de trimestre.']}
    if avisos:
        out['avisos'] = avisos
    cm.salida(out)


# =========================================================== pro forma

PONDERA = {'irr_tot': 'tf_total', 'irr_priv': 'tf_total', 'irr_cons': 'con_total',
           'irr_com': 'com_total', 'tf_s1': 'tf_total', 'tf_s2': 'tf_total', 'tf_s3': 'tf_total',
           'tf_s4': 'tf_total', 'tf_s5': 'tf_total', 'tf_irregular': 'tf_total',
           'con_s2': 'con_total', 'com_s2': 'com_total', 'roe': 'bPN', 'roe_ord': 'bPN',
           'tasa_prest': 'bPr', 'tasa_dep': 'bDe', 'prev_irr': 'tf_total'}


def cmd_proforma(a):
    """Suma hacia atrás entidades absorbidas a su absorbente (panel nominal, antes de preparar)."""
    df = cargar(a.panel)
    num = [c for c in df.columns if c not in ('periodo', 'codigo', 'entidad', 'tipo')]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    log = []
    for regla in a.fusion:
        if '=' not in regla:
            cm.salida({'error': 'Formato de --fusion: ABSORBENTE=CODIGO_ABSORBIDA (ej. Galicia=150)'}, 2)
        abs_q, abd_q = regla.split('=', 1)
        absorbente, absorbida = resolver(df, abs_q), resolver(df, abd_q)
        fa = df['codigo'] == absorbente
        fb = df['codigo'] == absorbida
        meses = sorted(set(df.loc[fb, 'periodo']) & set(df.loc[fa, 'periodo']))
        if not meses:
            log.append({'fusion': regla, 'aviso': 'sin meses en común'})
            continue
        A = df[fa].set_index('periodo')
        B = df[fb].set_index('periodo')
        for per in meses:
            ia = df.index[fa & (df['periodo'] == per)][0]
            b = B.loc[per]
            for c in num:
                bv = b.get(c, np.nan)
                av = A.loc[per].get(c, np.nan)
                if c in PONDERA and PONDERA[c] in df:
                    wa, wb = A.loc[per].get(PONDERA[c], np.nan), b.get(PONDERA[c], np.nan)
                    if av == av and bv == bv and wa == wa and wb == wb and wa + wb > 0:
                        df.at[ia, c] = (av * wa + bv * wb) / (wa + wb)
                elif bc.CAMPOS.get(c, (None, None, None, False))[3]:
                    if bv == bv:
                        df.at[ia, c] = bv if av != av else av + bv
                # el resto de los ratios queda como el del absorbente (se aclara en el JSON)
        df = df[~fb]
        log.append({'fusion': '%s <- %s' % (nombre(cargar(a.panel), absorbente), nombre(cargar(a.panel), absorbida)),
                    'meses_sumados': '%s a %s (%d)' % (meses[0], meses[-1], len(meses))})
    df.to_csv(a.salida, index=False)
    cm.salida({'archivo': os.path.abspath(a.salida), 'fusiones': log,
               'criterio': 'Montos y cantidades aditivos se suman. Moras y situaciones se ponderan por la '
                           'cartera; ROE por patrimonio; tasas implícitas por préstamos o depósitos. Los '
                           'demás indicadores del BCRA quedan como los del absorbente en los meses previos '
                           '(no leerlos como pro forma). Los agregados del sistema no cambian.',
               'siguiente_paso': 'Correr preparar sobre este panel y luego calidad: el salto de la fusión '
                                 'ya no debería aparecer.'})


# =========================================================== rentabilidad

COMPONENTES = [('margen_financiero', ['bIF', 'bEgF']), ('servicios_neto', ['bIS', 'bES']),
               ('incobrabilidad', ['bInc']), ('gastos_admin', ['bGA']), ('resultado_monetario', ['bRM']),
               ('impuesto_ganancias', ['bIG'])]


def flujo_12m(s, hasta):
    """Flujo de los últimos 12 meses a partir de acumulados del ejercicio (cierre en diciembre).
    LTM = YTD(hasta) + YTD(dic anterior) − YTD(mismo mes del año anterior). Si falta algo,
    anualiza el YTD (× 12 / mes)."""
    mes = int(hasta[5:7])
    ytd = s.get(hasta, np.nan)
    if ytd != ytd:
        return np.nan, 'sin dato'
    if mes == 12:
        return ytd, 'año calendario'
    dic = s.get('%04d-12' % (int(hasta[:4]) - 1), np.nan)
    prev = s.get(cm.mes_anterior(hasta, 12), np.nan)
    if dic == dic and prev == prev:
        return ytd + dic - prev, 'últimos 12 meses'
    return ytd * 12 / mes, 'acumulado anualizado'


def cmd_rentabilidad(a):
    df = cargar(a.datos)
    meta = meta_de(a.datos)
    exigir_campos(df, ['bRes', 'bA', 'bPN'])
    hasta = a.hasta or ultimo_con_dato(df, 'bRes')
    foco = resolver(df, a.foco) if a.foco else None
    pares = universo(df, a.pares, hasta, excluir=(foco,) if foco else ())
    ents = ([foco] if foco else []) + pares
    if a.segmentos:
        seg = pd.read_csv(a.segmentos, dtype={'codigo': str}).set_index('codigo')['cluster']
        ents = sorted(set(ents) | set(seg.index))
    meses12 = cm.meses_entre(cm.mes_anterior(hasta, 11), hasta)
    filas = []
    for cod in ents:
        g = df[df['codigo'] == cod].set_index('periodo')
        if g.empty:
            continue
        a_prom = g['bA'].reindex(meses12).mean()
        pn_prom = g['bPN'].reindex(meses12).mean()
        if not a_prom or a_prom != a_prom:
            continue
        fila = {'codigo': cod, 'entidad': nombre(df, cod), 'activo_prom': a_prom, 'pn_prom': pn_prom}
        suma = 0.0
        for comp, cols in COMPONENTES:
            v, base = 0.0, None
            for c in cols:
                if c in g:
                    f, base = flujo_12m(g[c], hasta)
                    v += 0 if f != f else f
            fila[comp] = 100 * v / a_prom
            suma += v
        res, base = flujo_12m(g['bRes'], hasta)
        fila['otros'] = 100 * (res - suma) / a_prom if res == res else np.nan
        fila['roa'] = 100 * res / a_prom if res == res else np.nan
        fila['roe'] = 100 * res / pn_prom if res == res and pn_prom else np.nan
        fila['apalancamiento_a_pn'] = a_prom / pn_prom if pn_prom else np.nan
        fila['base_flujo'] = base
        fila['resultado'] = res
        for comp, _ in COMPONENTES:
            fila[comp + '_monto'] = fila[comp] * a_prom / 100
        filas.append(fila)
    t = pd.DataFrame(filas).set_index('codigo')
    if t.empty:
        cm.salida({'error': 'Sin resultados para calcular rentabilidad'}, 2)
    comps = [c for c, _ in COMPONENTES] + ['otros', 'roa', 'roe']
    out = {'hasta': hasta, 'base': t['base_flujo'].mode().iloc[0],
           'definicion': 'Cada componente = flujo de 12 meses / activo promedio (en %, pesos constantes). '
                         'ROA = suma de componentes. ROE = resultado / patrimonio promedio. Incobrabilidad, '
                         'gastos, impuesto y (en general) resultado monetario restan.'}
    if foco and foco in t.index:
        pp = t.loc[[x for x in pares if x in t.index], comps]
        med = pp.median()
        f = t.loc[foco, comps]
        brecha = (f - med)
        out['foco'] = {'entidad': nombre(df, foco), 'componentes_pct_activo': redondear(f.to_dict(), 3)}
        out['mediana_pares'] = redondear(med.to_dict(), 3)
        out['brecha_pp_activo'] = redondear(brecha.to_dict(), 3)
        out['brecha_en_pesos'] = redondear({c: brecha[c] / 100 * t.loc[foco, 'activo_prom']
                                            for c in comps if c not in ('roe',)}, 1)
        mfn = lambda r: r['margen_financiero'] + r['resultado_monetario']  # noqa: E731
        out['margen_neto_de_inflacion'] = redondear({
            'foco': mfn(f), 'mediana_pares': float((pp['margen_financiero'] + pp['resultado_monetario']).median()),
            'nota': 'Con inflación, parte del margen financiero compensa la pérdida por exposición '
                    'monetaria: leer margen financiero + resultado monetario juntos.'}, 3)
        out['pares'] = [nombre(df, x) for x in pp.index]
        png = ruta_salida(a, 'rentabilidad_%s.png' % foco)
        nombres_c = {'margen_financiero': 'Margen financiero', 'servicios_neto': 'Comisiones netas',
                     'incobrabilidad': 'Cargo por incobrabilidad', 'gastos_admin': 'Gastos de administración',
                     'resultado_monetario': 'Resultado monetario (inflación)',
                     'impuesto_ganancias': 'Impuesto a las ganancias', 'otros': 'Otros', 'roa': 'ROA total'}
        vals = [(nombres_c[c], brecha[c]) for c in [c for c, _ in COMPONENTES] + ['otros', 'roa']]
        gr.barras_h(vals, 'De dónde sale la diferencia de ROA: %s vs mediana de pares' % gr.corto(nombre(df, foco)),
                    png, sufijo=' pp', dec=2, xlabel='Diferencia en puntos del activo (positivo = a favor del foco)',
                    fuente=fuente_txt(meta, '%s a %s. Pares: %s.' % (meses12[0], hasta, ', '.join(gr.corto(nombre(df, x), 14) for x in pp.index))))
        out['grafico'] = os.path.abspath(png)
    if a.segmentos:
        t['segmento'] = t.index.map(seg)
        agg = t.dropna(subset=['segmento']).groupby('segmento')
        pond = {}
        for sg, gg in agg:
            act = gg['activo_prom'].sum()
            pond[int(sg)] = {'n': len(gg),
                             'roe_ponderado': 100 * gg['resultado'].sum() / gg['pn_prom'].sum(),
                             'roa_ponderado': 100 * gg['resultado'].sum() / act,
                             'roe_mediano': float(gg['roe'].median()),
                             **{c + '_ponderado': 100 * gg[c + '_monto'].sum() / act for c, _ in COMPONENTES}}
        out['por_segmento'] = redondear(pond, 3)
        out['nota_segmentos'] = ('Ponderado = suma de resultados / suma de activos o patrimonios del '
                                 'segmento: lo que gana el segmento como negocio. La mediana describe al banco típico.')
    ruta = ruta_salida(a, 'rentabilidad.csv')
    t.reset_index().to_csv(ruta, index=False)
    out['detalle_csv'] = os.path.abspath(ruta)
    cm.salida(out)


# =========================================================== calidad

def cmd_calidad(a):
    df = cargar(a.datos)
    campos = a.campos or [c for c in (['bA', 'bPr', 'bPr_priv', 'bDe', 'bDe_priv', 'bPers', 'bHip',
                                       'bPrend', 'bDoc', 'bAdel', 'bCA', 'bPF', 'bCC', 'bPN']
                                      + CANTIDADES + ['irr_tot', 'irr_cons', 'irr_com', 'roe'])
                          if c in df]
    sis = df[df['codigo'] == 'AAA00'].set_index('periodo')
    tam = df.groupby('codigo')['cuota_bA'].median() if 'cuota_bA' in df else pd.Series(dtype=float)
    alertas, omitidas = [], 0
    limpio = df.copy()
    for cod, g in df.groupby('codigo'):
        chica = cod in tam.index and not np.isnan(tam[cod]) and tam[cod] < a.min_cuota
        g = g.sort_values('periodo').set_index('periodo')
        nom = g['entidad'].iloc[0]
        peso = tam.get(cod, 100.0) if cod in tam.index else 100.0
        for c in campos:
            s = pd.to_numeric(g[c], errors='coerce').dropna()
            if len(s) < 3:
                continue
            per = list(s.index)
            v = s.values
            tasa = es_tasa(c)
            saltar = set()
            for i in range(1, len(v)):
                if i in saltar or len(cm.meses_entre(per[i - 1], per[i])) - 1 > 3:
                    continue
                a0, a1 = v[i - 1], v[i]
                a2 = v[i + 1] if i + 1 < len(v) else None
                tipo = None
                if tasa:
                    salto = a1 - a0
                    if abs(salto) > a.umbral_pp and a2 is not None and abs(a2 - a0) < abs(salto) / 3:
                        tipo = 'pico aislado'
                    impacto = abs(salto) * (peso if peso == peso else 0) / 100
                else:
                    if a0 <= 0 or a1 <= 0:
                        continue
                    r = a1 / a0
                    if not (r > a.umbral or r < 1 / a.umbral):
                        continue
                    vuelve = a2 is not None and a2 > 0 and abs(math.log(a2 / a0)) < abs(math.log(r)) / 3
                    if vuelve:
                        tipo = 'pico aislado'
                    elif c in ('bA', 'bPr', 'bDe', 'bPN', 'bPr_priv', 'bDe_priv'):
                        tipo = 'salto persistente'
                    else:
                        tipo = 'salto'
                    tot = sis[c].get(per[i], np.nan) if c in sis else np.nan
                    impacto = 100 * abs(a1 - a0) / tot if tot and tot == tot else np.nan
                if not tipo:
                    continue
                if chica:
                    omitidas += 1
                    continue
                lectura = {'pico aislado': 'probable error de carga: excluir esa celda',
                           'salto persistente': 'posible fusión, adquisición o cambio de criterio: '
                                                'verificar antes de leerlo como crecimiento orgánico',
                           'salto': 'revisar: cambio de escala sin reversión'}[tipo]
                alertas.append({'tipo': tipo, 'entidad': nom, 'codigo': cod, 'campo': c,
                                'periodo': per[i], 'antes': a0, 'valor': a1, 'despues': a2,
                                'impacto_pp_sistema': impacto, 'lectura': lectura})
                if tipo == 'pico aislado':
                    saltar.add(i + 1)  # la vuelta al nivel previo es parte del mismo evento
                    limpio.loc[(limpio['codigo'] == cod) & (limpio['periodo'] == per[i]), c] = np.nan
    # Saltos de cuota de un mes que no se revierten: la firma de fusiones, adquisiciones,
    # el blanqueo de 2024 o cambios de criterio. Orgánicamente, la cuota se mueve despacio.
    for c in ('cuota_bA', 'cuota_bPr_priv', 'cuota_bDe_priv'):
        if c not in df:
            continue
        for cod, g in df[df['tipo'] != 'grupo'].groupby('codigo'):
            s = pd.to_numeric(g.set_index('periodo')[c], errors='coerce').dropna().sort_index()
            per, v = list(s.index), s.values
            for i in range(1, len(v)):
                d = v[i] - v[i - 1]
                if abs(d) < a.salto_cuota or v[i - 1] <= 0 or abs(d) / v[i - 1] < 0.08:
                    continue
                if i + 1 < len(v) and abs(v[i + 1] - v[i - 1]) < abs(d) / 3:
                    continue  # se revierte: es un pico, ya lo trata la regla anterior
                alertas.append({'tipo': 'salto de cuota', 'entidad': g['entidad'].iloc[0], 'codigo': cod,
                                'campo': c, 'periodo': per[i], 'antes': v[i - 1], 'valor': v[i],
                                'despues': v[i + 1] if i + 1 < len(v) else None,
                                'impacto_pp_sistema': abs(d),
                                'lectura': 'la cuota salta en un mes y no vuelve: posible fusión o '
                                           'adquisición, blanqueo, devaluación o cambio de criterio. '
                                           'Verificar antes de leerlo como ganancia comercial'})
    alertas.sort(key=lambda x: -(x['impacto_pp_sistema'] if x['impacto_pp_sistema'] == x['impacto_pp_sistema'] else 0))
    cobertura = {c: round(100 * df.loc[df['tipo'] != 'grupo', c].notna().mean(), 1) for c in campos}
    ruta = ruta_salida(a, 'calidad.csv')
    pd.DataFrame(alertas).to_csv(ruta, index=False)
    out = {'alertas': len(alertas), 'detalle_csv': os.path.abspath(ruta),
           'por_tipo': pd.Series([x['tipo'] for x in alertas]).value_counts().to_dict() if alertas else {},
           'omitidas_entidades_chicas': omitidas,
           'saltos_de_cuota': redondear([x for x in alertas if x['tipo'] == 'salto de cuota'][:15], 3),
           'principales_por_impacto': redondear([x for x in alertas if x['tipo'] != 'salto de cuota'][:25], 3),
           'cobertura_pct_celdas': cobertura,
           'criterio': 'Montos y cantidades: cambio mayor a x%s (o menor a 1/%s) entre meses. Tasas: '
                       'salto mayor a %s pp. "Pico aislado" = vuelve al nivel previo el período '
                       'siguiente. Orden: impacto sobre el total del sistema (pp). Se omiten entidades '
                       'con menos de %s %% del activo (ruido normal en bancos chicos).'
                       % (a.umbral, a.umbral, a.umbral_pp, a.min_cuota)}
    if a.limpiar:
        limpio.to_csv(a.limpiar, index=False)
        m = meta_de(a.datos)
        if m:
            with open(os.path.splitext(a.limpiar)[0] + '.meta.json', 'w') as f:
                json.dump(m, f, ensure_ascii=False, indent=1)
        out['limpio'] = os.path.abspath(a.limpiar)
        out['nota'] = ('En el archivo limpio los picos aislados quedan en blanco. Los derivados '
                       '(cuotas, mix) de esas celdas siguen calculados con el valor original: si el '
                       'pico afecta un derivado que se va a usar, excluir ese período del análisis.')
    cm.salida(out)


# =========================================================== cuotas

def cmd_cuotas(a):
    if len(a.campo) > 1:
        return cuotas_mapa(a)
    a.campo = a.campo[0]
    df = cargar(a.datos)
    meta = meta_de(a.datos)
    c = a.campo
    exigir_campos(df, [c])
    hasta = periodo_cercano(df, c, a.hasta or df['periodo'].max())
    desde = periodo_cercano(df, c, a.desde or cm.mes_anterior(hasta, 12))
    if not hasta or not desde or desde >= hasta:
        cm.salida({'error': 'No hay dos períodos con dato de %s en el rango' % c}, 2)
    sis = df[df['codigo'] == 'AAA00'].set_index('periodo')[c]
    M0, M1 = sis.get(desde), sis.get(hasta)
    if not M0 or not M1 or np.isnan(M0) or np.isnan(M1):
        cm.salida({'error': 'Falta el total del sistema para %s en %s o %s' % (c, desde, hasta)}, 2)
    foco = resolver(df, a.foco) if a.foco else None
    ents = universo(df, a.universo, hasta)
    filas = []
    piv = df[df['codigo'].isin(ents)].pivot_table(index='periodo', columns='codigo', values=c)
    sis_m = sis.reindex(piv.index)
    for cod in ents:
        if cod not in piv:
            continue
        v0, v1 = piv[cod].get(desde), piv[cod].get(hasta)
        if v0 is None or v1 is None or np.isnan(v0) or np.isnan(v1) or v0 <= 0:
            continue
        s0, s1 = 100 * v0 / M0, 100 * v1 / M1
        sh = (100 * piv[cod] / sis_m).dropna()
        sh = sh[sh.index <= hasta].tail(6)
        pend = float(np.polyfit(range(len(sh)), sh.values, 1)[0]) if len(sh) >= 3 else np.nan
        filas.append({'codigo': cod, 'entidad': nombre(df, cod), 'valor_desde': v0, 'valor_hasta': v1,
                      'cuota_desde': s0, 'cuota_hasta': s1, 'cambio_pp': s1 - s0,
                      'crec_real_pct': 100 * (v1 / v0 - 1), 'efecto_cuota_pct': 100 * (s1 / s0 - 1),
                      'pendiente_cuota_pp_mes_ult6': pend})
    t = pd.DataFrame(filas)
    if t.empty:
        cm.salida({'error': 'Sin entidades con dato en ambos períodos'}, 2)
    t['rank_desde'] = t['cuota_desde'].rank(ascending=False, method='min').astype(int)
    t['rank_hasta'] = t['cuota_hasta'].rank(ascending=False, method='min').astype(int)
    t = t.sort_values('cambio_pp', ascending=False)
    hhi0 = float((t['cuota_desde'] ** 2).sum())
    hhi1 = float((t['cuota_hasta'] ** 2).sum())
    cr5_0 = float(t['cuota_desde'].nlargest(5).sum())
    cr5_1 = float(t['cuota_hasta'].nlargest(5).sum())
    gm = 100 * (M1 / M0 - 1)
    ruta = ruta_salida(a, 'cuotas_%s.csv' % c)
    t.to_csv(ruta, index=False)
    graf = t.reindex(t['cambio_pp'].abs().sort_values(ascending=False).index).head(a.top)
    if foco is not None and foco not in set(graf['codigo']):
        graf = pd.concat([graf, t[t['codigo'] == foco]])
    graf = graf.sort_values('cambio_pp', ascending=False)
    png = ruta_salida(a, 'cuotas_%s.png' % c)
    gr.barras_h(list(zip(graf['entidad'], graf['cambio_pp'])),
                'Quién ganó y quién perdió cuota en %s' % descripcion(c).lower(), png,
                foco=nombre(df, foco) if foco else None, sufijo=' pp', dec=2,
                fuente=fuente_txt(meta, 'Cambio de cuota entre %s y %s.' % (desde, hasta)),
                xlabel='Cambio de cuota de mercado (puntos porcentuales)')
    out = {'campo': c, 'desc': descripcion(c), 'desde': desde, 'hasta': hasta,
           'mercado': {'crec_real_pct' if meta.get('deflactado') else 'crec_nominal_pct': gm,
                       'hhi_desde': hhi0, 'hhi_hasta': hhi1, 'cr5_desde': cr5_0, 'cr5_hasta': cr5_1,
                       'universo': a.universo, 'entidades': len(t),
                       'cuota_universo_hasta': float(t['cuota_hasta'].sum())},
           'ganadores': redondear(t.head(a.top).to_dict('records'), 3),
           'perdedores': redondear(t.tail(a.top).iloc[::-1].to_dict('records'), 3),
           'identidad': '(1 + crecimiento de la entidad) = (1 + crecimiento del mercado) × (1 + efecto cuota)',
           'grafico': os.path.abspath(png), 'detalle_csv': os.path.abspath(ruta)}
    if foco is not None:
        fila = t[t['codigo'] == foco]
        out['foco'] = redondear(fila.to_dict('records')[0], 3) if len(fila) else 'sin dato'
    if not meta.get('deflactado'):
        out['aviso'] = 'Montos nominales: el crecimiento no está ajustado por inflación.'
    cm.salida(out)


def cuotas_mapa(a):
    """Cambio de cuota (pp) de varias entidades en varios productos a la vez."""
    df = cargar(a.datos)
    meta = meta_de(a.datos)
    exigir_campos(df, a.campo)
    hasta_g = a.hasta or df.loc[df['tipo'] != 'grupo', 'periodo'].max()
    foco = resolver(df, a.foco) if a.foco else None
    if a.entidades:
        ents = [resolver(df, e) for e in a.entidades]
    else:
        ents = universo(df, 'top7', hasta_g)
    if foco and foco not in ents:
        ents = [foco] + ents
    sis = df[df['codigo'] == 'AAA00'].set_index('periodo')
    mat, cuota_fin, filas = [], [], []
    for cod in ents:
        fila_d, fila_c = [], []
        for c in a.campo:
            h = periodo_cercano(df, c, hasta_g)
            d0 = periodo_cercano(df, c, a.desde or cm.mes_anterior(h, 24))
            s = df[df['codigo'] == cod].set_index('periodo')[c]
            v0, v1 = s.get(d0, np.nan), s.get(h, np.nan)
            m0, m1 = sis[c].get(d0, np.nan), sis[c].get(h, np.nan)
            s0 = 100 * v0 / m0 if m0 and m0 == m0 else np.nan
            s1 = 100 * v1 / m1 if m1 and m1 == m1 else np.nan
            fila_d.append(s1 - s0)
            fila_c.append(s1)
            filas.append({'entidad': nombre(df, cod), 'campo': c, 'desde': d0, 'hasta': h,
                          'cuota_desde': s0, 'cuota_hasta': s1, 'cambio_pp': s1 - s0})
        mat.append(fila_d)
        cuota_fin.append(fila_c)
    m = np.array(mat, dtype=float)
    # escala al percentil 90 para que un caso extremo no apague al resto (las celdas igual muestran el valor)
    vmax = float(np.nanpercentile(np.abs(m), 90)) if np.isfinite(m).any() else 1
    ano = [['%s\n(%s)' % (gr.num(m[i, j], 1), gr.num(cuota_fin[i][j], 1)) if m[i, j] == m[i, j] else ''
            for j in range(len(a.campo))] for i in range(len(ents))]
    png = ruta_salida(a, 'mapa_cuotas.png')
    gr.heatmap(m, [gr.corto(nombre(df, e), 22) for e in ents], [PRODUCTOS.get(c, c) for c in a.campo],
               'Cambio de cuota por producto (pp)', png, anotaciones=ano, vmax=max(vmax, 0.5),
               positivo_azul=True,
               fuente=fuente_txt(meta, 'Celda: cambio en pp (cuota final entre paréntesis). Desde %s hasta %s '
                                       '(o el último trimestre con dato).' % (a.desde or '24 meses antes', hasta_g)))
    ruta = ruta_salida(a, 'mapa_cuotas.csv')
    pd.DataFrame(filas).to_csv(ruta, index=False)
    cm.salida({'productos': a.campo, 'entidades': [nombre(df, e) for e in ents],
               'detalle': redondear(filas, 3), 'grafico': os.path.abspath(png),
               'detalle_csv': os.path.abspath(ruta),
               'como_leer': 'Azul = ganó cuota, rojo = perdió. Revisar con calidad (saltos de cuota) antes de '
                            'atribuir un cambio a gestión comercial.'})


# =========================================================== brechas

def cmd_brechas(a):
    df = cargar(a.datos)
    meta = meta_de(a.datos)
    foco = resolver(df, a.foco)
    fecha = a.fecha or ultimo_con_dato(df, 'bA')
    pares = universo(df, a.pares, fecha, excluir=(foco,))
    metricas = [m for m in (a.metricas or BRECHAS_DEFECTO) if m in df]
    filas, puntos = [], []
    for m in metricas:
        per = periodo_cercano(df[df['codigo'].isin(pares + [foco])], m, fecha)
        if not per:
            continue
        d = df[df['periodo'] == per].set_index('codigo')[m]
        fv = d.get(foco, np.nan)
        pv = d.reindex(pares).dropna()
        if len(pv) < 3:
            continue
        p25, med, p75 = np.percentile(pv, [25, 50, 75])
        pct = float(stats.percentileofscore(pv, fv, kind='mean')) if not np.isnan(fv) else np.nan
        mejor = MEJOR.get(m)
        lectura = 'elección de modelo'
        if mejor is not None and not np.isnan(pct):
            bueno = pct >= 50 if mejor else pct <= 50
            fuerte = pct >= 75 if mejor else pct <= 25
            debil = pct <= 25 if mejor else pct >= 75
            lectura = 'fortaleza' if fuerte else ('debilidad' if debil else ('mejor que la mediana' if bueno else 'peor que la mediana'))
        filas.append({'metrica': m, 'desc': descripcion(m), 'unidad': unidad(m), 'periodo': per,
                      'foco': fv, 'mediana_pares': med, 'p25': p25, 'p75': p75,
                      'min': float(pv.min()), 'max': float(pv.max()), 'percentil_foco': pct,
                      'brecha_vs_mediana': fv - med if not np.isnan(fv) else np.nan,
                      'n_pares': int(len(pv)), 'lectura': lectura})
        dec = 0 if abs(med) >= 1000 else (2 if abs(med) < 10 else 1)
        puntos.append((m, 25, 50, 75, pct, mejor,
                       '%s %s · med. %s' % (gr.corto(nombre(df, foco), 12), gr.num(fv, dec), gr.num(med, dec))))

    # Oportunidades dimensionadas
    ops = []
    fila_f = df[(df['codigo'] == foco)].set_index('periodo')
    for mx, comp in (('mix_pers', 'bPers'), ('mix_hip', 'bHip'), ('mix_prend', 'bPrend'),
                     ('mix_doc', 'bDoc'), ('mix_adel', 'bAdel')):
        f = next((x for x in filas if x['metrica'] == mx), None)
        if not f or np.isnan(f['foco']) or f['foco'] >= f['mediana_pares']:
            continue
        base = fila_f['bPr_priv'].get(f['periodo'], np.nan)
        val = (f['mediana_pares'] - f['foco']) / 100 * base
        ops.append({'tipo': 'mix de cartera', 'producto': comp, 'valor': val,
                    'unidad': 'millones de pesos' + (' de %s' % meta['base'] if meta.get('base') else ''),
                    'lectura': 'stock adicional de %s si tuviera el mix mediano de los pares '
                               '(%s %% vs %s %%), con la misma cartera total'
                               % (descripcion(comp).lower(), gr.num(f['foco'], 1), gr.num(f['mediana_pares'], 1)),
                    'formula': '(mediana pares − foco) × préstamos privados del foco'})
    for met, base_col, unid, texto in (('pers_por_remu', 'remu', 'millones de pesos', 'préstamos personales'),
                                       ('saldo_ca_prom', 'cah', 'millones de pesos', 'saldos en caja de ahorros'),
                                       ('pla_por_tit', 'tit', 'tarjetas', 'tarjetas de crédito')):
        f = next((x for x in filas if x['metrica'] == met), None)
        if not f or np.isnan(f['foco']) or f['foco'] >= f['mediana_pares']:
            continue
        base = fila_f[base_col].get(f['periodo'], np.nan) if base_col in fila_f else np.nan
        k = 1e6 if unid == 'millones de pesos' else 1
        val = (f['mediana_pares'] - f['foco']) * base / k
        ops.append({'tipo': 'penetración', 'producto': met, 'valor': val, 'unidad': unid,
                    'lectura': '%s adicionales si llevara %s a la mediana de los pares sobre su propia base de %s'
                               % (texto, descripcion(met).lower(), descripcion(base_col).lower()),
                    'formula': '(mediana pares − foco) × %s del foco' % base_col})
    sis = df[df['codigo'] == 'AAA00'].set_index('periodo')
    for b, o, texto in FAIR_SHARE:
        cb, co = 'cuota_' + b, 'cuota_' + o
        if cb not in df or co not in df:
            continue
        pb = periodo_cercano(df[df['codigo'] == foco], cb, fecha)
        po = periodo_cercano(df[df['codigo'] == foco], co, fecha)
        if not pb or not po:
            continue
        sb, so = fila_f[cb].get(pb), fila_f[co].get(po)
        if sb is None or so is None or np.isnan(sb) or np.isnan(so) or sb <= so:
            continue
        tot = sis[o].get(po, np.nan)
        unid = unidad(o)
        val = (sb - so) / 100 * tot
        ops.append({'tipo': 'fair share', 'producto': o, 'valor': val,
                    'unidad': unid + (' de %s' % meta['base'] if meta.get('base') and unid == 'millones de pesos' else ''),
                    'lectura': 'si pudiera %s: cuota %s %s %% (%s) vs %s %s %% (%s)'
                               % (texto, b, gr.num(sb, 2), pb, o, gr.num(so, 2), po),
                    'formula': '(cuota %s − cuota %s) × total del sistema de %s' % (b, o, o)})
    for o in ops:
        v = o['valor']
        o['escenarios'] = {'conservador_25': v * 0.25, 'base_50': v * 0.5, 'cota_100': v} if v == v else {}
    t = pd.DataFrame(filas)
    ruta = ruta_salida(a, 'brechas_%s.csv' % foco)
    t.to_csv(ruta, index=False)
    png = ruta_salida(a, 'brechas_%s.png' % foco)
    gr.benchmark([(corta(p[0]), p[1], p[2], p[3], p[4], p[5]) for p in puntos],
                 '%s frente a sus pares' % gr.corto(nombre(df, foco)), png, nombre(df, foco),
                 textos=[p[6] for p in puntos],
                 fuente=fuente_txt(meta, 'Pares: %s (%d entidades), %s.' % (a.pares if isinstance(a.pares, str) else 'lista', len(pares), fecha)))
    out = {'foco': nombre(df, foco), 'fecha': fecha, 'pares': [nombre(df, p) for p in pares],
           'fortalezas': [x['metrica'] for x in filas if x['lectura'] == 'fortaleza'],
           'debilidades': [x['metrica'] for x in filas if x['lectura'] == 'debilidad'],
           'metricas': redondear(filas, 3),
           'oportunidades': redondear(sorted(ops, key=lambda x: (x['unidad'], -(x['valor'] or 0))), 1),
           'aviso_oportunidades': 'Son cotas de referencia (qué pasaría si se pareciera a la mediana o '
                                  'a su cuota natural), no pronósticos: validar apetito de riesgo, '
                                  'canal y rentabilidad antes de convertirlas en metas.',
           'grafico': os.path.abspath(png), 'detalle_csv': os.path.abspath(ruta)}
    cm.salida(out)


# =========================================================== correlación

# Pares que se mueven juntos por construcción contable, no por un mecanismo económico: se
# informan aparte para no presentarlos como hallazgos.
FAMILIAS_CONTABLES = [
    {'irr_tot', 'irr_cons', 'irr_com', 'irr_priv', 'tf_irregular', 'perdida_s2a5', 'perdida_s3a5',
     'prev_irr', 'exc_prev', 'costo_riesgo', 'roa_inco', 'bInc', 'bPrev', 'irr_cons_sin_dilucion'},
    {'roe', 'roe_ord', 'roa', 'roa_aig', 'bRes'},
    {'bA', 'bP', 'bPN', 'pn_activo', 'apalancamiento', 'log_activo'},
]


def base_campo(c):
    c = c.split(':')[0]
    for pre in ('cuota_', 'mix_'):
        if c.startswith(pre):
            c = c[len(pre):]
    return c[:-3] if c.endswith('_ia') else c


def relacion_contable(x, y):
    bx, by = base_campo(x), base_campo(y)
    if bx == by:
        return True
    return any(bx in f and by in f for f in FAMILIAS_CONTABLES)


def cmd_correlacion(a):
    df = cargar(a.datos)
    meta = meta_de(a.datos)
    if a.modo == 'transversal':
        return correlacion_transversal(a, df, meta)
    exigir_campos(df, a.variables)
    ent = resolver(df, a.entidad)
    datos = {}
    for v in a.variables:
        datos[v] = a_mensual(serie(df, ent, v.split(':')[0]))
    mac = None
    if a.macro_vars:
        if not a.macro:
            cm.salida({'error': '--macro-vars requiere --macro macro.csv'}, 2)
        mac = pd.read_csv(a.macro, dtype={'periodo': str}).set_index('periodo')
        faltan = [x.split(':')[0] for x in a.macro_vars if x.split(':')[0] not in mac]
        if faltan:
            cm.salida({'error': 'Variables macro que no están en el CSV: %s' % faltan}, 2)
        for x in a.macro_vars:
            datos[x] = a_mensual(pd.to_numeric(mac[x.split(':')[0]], errors='coerce'))
    idx = sorted(set().union(*[set(s.index) for s in datos.values()]))
    idx = cm.meses_entre(idx[0], idx[-1])
    # Las series bancarias se excluyen antes de transformar; las macro no (sus valores son genuinos)
    tr = {k: transformar(excluir(s.reindex(idx), a.excluir) if k in a.variables else s.reindex(idx),
                         k, a.transform) for k, s in datos.items()}
    ctrl = None
    if a.controles:
        if mac is None:
            mac = pd.read_csv(a.macro, dtype={'periodo': str}).set_index('periodo')
        ctrl = pd.concat([transformar(a_mensual(pd.to_numeric(mac[c.split(':')[0]], errors='coerce'))
                                      .reindex(idx), c, a.transform).rename(c) for c in a.controles], axis=1)

    if a.desde or a.hasta:
        lo, hi = a.desde or idx[0], a.hasta or idx[-1]
        tr = {k: v[(v.index >= lo) & (v.index <= hi)] for k, v in tr.items()}
        if ctrl is not None:
            ctrl = ctrl[(ctrl.index >= lo) & (ctrl.index <= hi)]
        idx = [m for m in idx if lo <= m <= hi]

    def resid(s):
        """Residuo de s contra los controles (correlación parcial)."""
        if ctrl is None:
            return s
        d = pd.concat([s.rename('_s'), ctrl], axis=1).dropna()
        if len(d) < 8:
            return s.iloc[0:0]
        X = np.column_stack([np.ones(len(d))] + [d[c].values for c in ctrl.columns])
        beta = np.linalg.lstsq(X, d['_s'].values, rcond=None)[0]
        return pd.Series(d['_s'].values - X @ beta, index=d.index)
    ys = a.variables
    xs = a.macro_vars or a.variables
    pruebas = []
    for y in ys:
        for x in xs:
            if x == y or (not a.macro_vars and xs.index(x) <= ys.index(y)):
                continue
            for k in range(0, a.rezagos + 1):
                res = corr_neff(resid(tr[x].shift(k)), resid(tr[y]))
                if res:
                    res.update({'y': y, 'x': x, 'rezago_meses': k})
                    pruebas.append(res)
    if not pruebas:
        cm.salida({'error': 'Sin pares con al menos 8 observaciones comunes',
                   'ayuda': 'Ampliar el panel en el tiempo (--meses en panel.py) o usar transform mensual'}, 2)
    q = bh([p['p'] for p in pruebas])
    for p, qq in zip(pruebas, q):
        p['q'] = float(qq)
    t = pd.DataFrame(pruebas)
    mejores = t.loc[t.groupby(['y', 'x'])['r'].apply(lambda s: s.abs().idxmax())]
    mejores = mejores.reindex(mejores['r'].abs().sort_values(ascending=False).index)
    ruta = ruta_salida(a, 'correlacion_%s.csv' % ent)
    t.to_csv(ruta, index=False)
    filas_y = list(dict.fromkeys(mejores['y']))
    cols_x = list(dict.fromkeys(mejores['x']))
    mat = np.full((len(filas_y), len(cols_x)), np.nan)
    ano = [[''] * len(cols_x) for _ in filas_y]
    for r in mejores.itertuples():
        i, j = filas_y.index(r.y), cols_x.index(r.x)
        mat[i, j] = r.r
        ano[i][j] = '%s\n%dm%s' % (gr.num(r.r, 2), r.rezago_meses, '*' if r.q < 0.1 else '')
    png = ruta_salida(a, 'correlacion_%s.png' % ent)
    gr.heatmap(mat, filas_y, cols_x, 'Correlación (mejor rezago) — %s' % gr.corto(nombre(df, ent), 30), png,
               anotaciones=ano,
               fuente=fuente_txt(meta, 'Series transformadas (%s). * = q < 0,10 tras corregir por '
                                       'comparaciones múltiples. "Nm" = la variable de la columna '
                                       'adelanta N meses.' % a.transform))
    lista, contables = [], []
    for r in mejores.itertuples():
        if relacion_contable(r.y, r.x):
            contables.append({'y': r.y, 'x': r.x, 'r': round(float(r.r), 3)})
            continue
        if len(lista) >= 25:
            continue
        sig = 'robusta' if r.q < 0.05 else ('indicio' if r.q < 0.2 else 'no concluyente')
        lista.append({'y': r.y, 'x': r.x, 'r': r.r, 'rho_spearman': r.rho,
                      'rezago_meses': r.rezago_meses, 'n': r.n, 'n_efectivo': r.n_ef, 'p': r.p,
                      'q': r.q, 'evidencia': sig,
                      'transformacion': '%s / %s' % (etiqueta_tr(r.y, a.transform), etiqueta_tr(r.x, a.transform)),
                      'lectura': '%s %s cuando %s %s%s' % (
                          r.y, 'sube' if r.r > 0 else 'baja', r.x, 'sube',
                          (' (con %d meses de anticipación)' % r.rezago_meses) if r.rezago_meses else ' (en simultáneo)')})
    neff_med = float(mejores['n_ef'].median())
    out = {'entidad': nombre(df, ent), 'modo': 'temporal', 'transformacion': a.transform,
           'controles': a.controles or [],
           'periodo': '%s a %s' % (idx[0], idx[-1]), 'pruebas': len(t), 'mejores': redondear(lista, 3),
           'relaciones_contables': contables or None,
           'como_leer': 'r sobre variaciones (no niveles) para evitar correlaciones espurias por '
                        'tendencia/inflación; n_efectivo descuenta la autocorrelación; q corrige por '
                        'haber probado muchos pares y rezagos. Correlación no es causalidad. '
                        '"relaciones_contables": pares que se mueven juntos por construcción (por '
                        'ejemplo mora y cobertura, ROE y ROA, un saldo y su cuota): no son hallazgos.',
           'grafico': os.path.abspath(png), 'detalle_csv': os.path.abspath(ruta)}
    avisos = []
    if len(idx) < 36:
        avisos.append('Menos de 36 meses: resultados frágiles; ampliar la historia si es posible.')
    if neff_med < 12:
        avisos.append('n efectivo mediano %s: las variaciones de 12 meses se solapan y casi no hay '
                      'observaciones independientes. Repetir con --transform mensual y con más años '
                      'de historia antes de concluir.' % gr.num(neff_med, 1))
    if meta.get('deflactado') and not a.controles:
        avisos.append('Series en pesos constantes comparten el deflactor (IPC): parte de la '
                      'correlación entre montos reales puede ser mecánica. Repetir con '
                      '--controles inflacion_m:nivel para ver si sobrevive.')
    if avisos:
        out['avisos'] = avisos
    cm.salida(out)


def correlacion_transversal(a, df, meta):
    exigir_campos(df, a.variables)
    fecha = a.fecha or ultimo_con_dato(df, a.variables[0].split(':')[0])
    ents = universo(df, a.universo, fecha)
    meses = cm.meses_entre(cm.mes_anterior(fecha, max(1, a.ventana) - 1), fecha)
    d = df[df['codigo'].isin(ents) & df['periodo'].isin(meses)]
    vs = [v.split(':')[0] for v in a.variables]
    x = d.groupby('codigo')[vs].mean()
    if a.min_cuota and 'cuota_bA' in df:
        tam = d.groupby('codigo')['cuota_bA'].mean()
        x = x[tam.reindex(x.index) >= a.min_cuota]
    filas, mat, ano = [], np.full((len(vs), len(vs)), np.nan), [[''] * len(vs) for _ in vs]
    for i, v1 in enumerate(vs):
        for j, v2 in enumerate(vs):
            dd = x[[v1, v2]].dropna()
            if len(dd) < 6:
                continue
            if i == j:
                mat[i, j] = 1
                ano[i][j] = '1'
                continue
            rho, p = stats.spearmanr(dd[v1], dd[v2])
            mat[i, j] = rho
            ano[i][j] = '%s%s' % (gr.num(rho, 2), '*' if p < 0.05 else '')
            if j > i:
                filas.append({'a': v1, 'b': v2, 'rho_spearman': float(rho), 'p': float(p), 'n': len(dd)})
    if not filas:
        cm.salida({'error': 'Menos de 6 entidades con dato en las variables pedidas'}, 2)
    q = bh([f['p'] for f in filas])
    for f, qq in zip(filas, q):
        f['q'] = float(qq)
    filas.sort(key=lambda f: -abs(f['rho_spearman']))
    png = ruta_salida(a, 'correlacion_transversal.png')
    gr.heatmap(mat, vs, vs, 'Qué se mueve junto entre bancos (Spearman)', png, anotaciones=ano,
               fuente=fuente_txt(meta, 'Promedio %s a %s, %d entidades. * = p < 0,05.' % (meses[0], fecha, len(x))))
    ruta = ruta_salida(a, 'correlacion_transversal.csv')
    pd.DataFrame(filas).to_csv(ruta, index=False)
    contables = [{'a': f['a'], 'b': f['b'], 'rho_spearman': round(f['rho_spearman'], 3)}
                 for f in filas if relacion_contable(f['a'], f['b'])]
    filas = [f for f in filas if not relacion_contable(f['a'], f['b'])]
    cm.salida({'modo': 'transversal', 'periodo': '%s a %s' % (meses[0], fecha), 'entidades': len(x),
               'pares': redondear(filas[:30], 3), 'relaciones_contables': contables or None,
               'como_leer': 'Spearman (por rangos) entre bancos: robusto a outliers de tamaño. Con ~%d '
                            'bancos, |rho| < 0,3 suele ser ruido. Describe asociaciones entre modelos '
                            'de negocio, no causalidad. "relaciones_contables" se mueven juntos por '
                            'construcción y no son hallazgos.' % len(x),
               'grafico': os.path.abspath(png), 'detalle_csv': os.path.abspath(ruta)})


# =========================================================== segmentar

def cmd_segmentar(a):
    from sklearn.cluster import AgglomerativeClustering, KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import adjusted_rand_score, silhouette_samples, silhouette_score
    df = cargar(a.datos)
    meta = meta_de(a.datos)
    fecha = a.fecha or ultimo_con_dato(df, 'bA')
    meses = cm.meses_entre(cm.mes_anterior(fecha, max(1, a.ventana) - 1), fecha)
    ents = universo(df, a.universo, fecha)
    d = df[df['codigo'].isin(ents) & df['periodo'].isin(meses)]
    vars_ = [v for v in (a.variables or SEG_DEFECTO) if v in df]
    res_vars = [v for v in (a.resultados or SEG_RESULTADOS) if v in df]
    x = d.groupby('codigo')[vars_ + [v for v in res_vars if v not in vars_] +
                            [c for c in ('bA', 'bPr_priv', 'bDe_priv', 'cuota_bA') if c in df]].mean()
    if 'cuota_bA' in x and a.min_cuota:
        x = x[x['cuota_bA'] >= a.min_cuota]
    if 'bPr_priv' in x:
        x = x[x['bPr_priv'] > 0]
    usar = [v for v in vars_ if x[v].notna().mean() >= 0.6]
    descartadas = [v for v in vars_ if v not in usar]
    x = x[x[usar].notna().mean(axis=1) >= 0.7]
    if len(x) < 8:
        cm.salida({'error': 'Muy pocas entidades para segmentar (%d)' % len(x)}, 2)
    z = x[usar].copy()
    z = z.fillna(z.median())
    lo, hi = z.quantile(0.05), z.quantile(0.95)
    z = z.clip(lo, hi, axis=1)
    z = (z - z.mean()) / z.std(ddof=0).replace(0, 1)
    ks = list(range(2, min(8, len(z) // 3) + 1)) if a.k == 'auto' else [int(a.k)]
    evals = {}
    for k in ks:
        km = KMeans(n_clusters=k, n_init=20, random_state=0).fit(z)
        tam = np.bincount(km.labels_)
        evals[k] = (silhouette_score(z, km.labels_), tam.min(), km)
    validos = {k: v for k, v in evals.items() if v[1] >= 2} or evals
    k = max(validos, key=lambda kk: (round(validos[kk][0], 2), -kk))
    # k = 2 casi siempre "gana" y solo separa grandes de chicos: si un k entre 3 y 6 queda a
    # menos de 0,03 de silhouette, se prefiere esa partición más informativa.
    if a.k == 'auto' and k == 2:
        alt = [kk for kk in validos if 3 <= kk <= 6 and validos[kk][0] >= validos[2][0] - 0.03]
        if alt:
            k = max(alt, key=lambda kk: validos[kk][0])
    km = validos[k][2]
    lab = km.labels_
    ward = AgglomerativeClustering(n_clusters=k, linkage='ward').fit(z).labels_
    ari_ward = adjusted_rand_score(lab, ward)
    rng = np.random.RandomState(0)
    aris = []
    for _ in range(30):
        idx = rng.choice(len(z), int(0.8 * len(z)), replace=False)
        sub = KMeans(n_clusters=k, n_init=10, random_state=0).fit(z.iloc[idx])
        aris.append(adjusted_rand_score(lab[idx], sub.labels_))
    sil = silhouette_samples(z, lab)
    x['cluster'] = lab + 1
    x['silhouette'] = sil
    x['entidad'] = [nombre(df, c) for c in x.index]
    perfiles = []
    tot = {c: x[c].sum() for c in ('bA', 'bPr_priv', 'bDe_priv') if c in x}
    for cl in sorted(x['cluster'].unique()):
        m = x['cluster'] == cl
        zc = z[m.values].mean()
        rasgos = zc.sort_values(key=lambda s: -s.abs())
        perfil = {'cluster': int(cl), 'n': int(m.sum()),
                  'rasgos': ['%s %s (z %s)' % ('alto' if v > 0 else 'bajo', k_, gr.num(v, 1))
                             for k_, v in rasgos.head(4).items()],
                  'miembros': list(x.loc[m].sort_values('bA', ascending=False)['entidad'].map(lambda s: gr.corto(s, 30)))
                  if 'bA' in x else list(x.loc[m, 'entidad']),
                  'medianas_modelo': {v: float(x.loc[m, v].median()) for v in usar},
                  'desempeño_mediano': {v: float(x.loc[m, v].median()) for v in res_vars if v in x}}
        for c, tv in tot.items():
            perfil['peso_en_universo_%s_pct' % c] = float(100 * x.loc[m, c].sum() / tv) if tv else None
        perfiles.append(perfil)
    pca = PCA(n_components=2).fit(z)
    pcs = pca.transform(z)
    x['pc1'], x['pc2'] = pcs[:, 0], pcs[:, 1]
    carga = pd.DataFrame(pca.components_.T, index=usar, columns=['pc1', 'pc2'])

    def eje(c):
        top = carga[c].sort_values(key=lambda s: -s.abs()).head(3)
        return ', '.join('%s%s' % ('+' if v > 0 else '−', i) for i, v in top.items())
    out_foco = None
    if a.foco:
        f = resolver(df, a.foco)
        if f in z.index:
            dist = np.sqrt(((z - z.loc[f]) ** 2).sum(axis=1)).drop(f).sort_values()
            out_foco = {'entidad': nombre(df, f), 'cluster': int(x.loc[f, 'cluster']),
                        'silhouette': float(x.loc[f, 'silhouette']),
                        'pares_reales_por_modelo': [{'entidad': nombre(df, c), 'distancia': float(v),
                                                     'cluster': int(x.loc[c, 'cluster'])}
                                                    for c, v in dist.head(6).items()]}
        else:
            out_foco = 'el foco quedó fuera (sin datos suficientes o bajo el umbral de tamaño)'
    ruta = ruta_salida(a, 'segmentos.csv')
    x.reset_index().to_csv(ruta, index=False)
    png = ruta_salida(a, 'segmentos.png')
    xx = x.reset_index()
    xx['segmento'] = xx['cluster'].map(lambda c: 'Segmento %d' % c)
    foco_nom = out_foco['entidad'] if isinstance(out_foco, dict) else None
    gr.dispersion(xx, 'pc1', 'pc2', 'Mapa de modelos de negocio (%d segmentos)' % k, png,
                  tamano='bA' if 'bA' in xx else None, foco=foco_nom, color='segmento',
                  fuente=fuente_txt(meta, 'k-means sobre %d variables estandarizadas, promedio %s a %s.'
                                    % (len(usar), meses[0], fecha)),
                  xlabel='Componente 1 (%s %%): %s' % (gr.num(100 * pca.explained_variance_ratio_[0], 0), eje('pc1')),
                  ylabel='Componente 2 (%s %%): %s' % (gr.num(100 * pca.explained_variance_ratio_[1], 0), eje('pc2')),
                  n_etiquetas=14)
    transicion = x[x['silhouette'] < 0.05].sort_values('silhouette')
    out = {'periodo': '%s a %s' % (meses[0], fecha), 'entidades': len(x), 'k': k,
           'silhouette_por_k': {kk: round(v[0], 3) for kk, v in evals.items()},
           'calidad': {'silhouette': float(validos[k][0]), 'acuerdo_con_ward_ari': float(ari_ward),
                       'estabilidad_bootstrap_ari': float(np.mean(aris))},
           'variables_modelo': usar, 'variables_descartadas_por_faltantes': descartadas,
           'segmentos': redondear(perfiles, 2),
           'en_transicion': [{'entidad': r.entidad, 'cluster': int(r.cluster), 'silhouette': round(float(r.silhouette), 3)}
                             for r in transicion.itertuples()],
           'como_leer': 'silhouette > 0,5 estructura clara; 0,25-0,5 razonable; < 0,25 débil (los '
                        'segmentos son una simplificación). Estabilidad ARI > 0,7 = segmentos robustos. '
                        'Bancos "en transición" (silhouette ~0) están entre dos modelos: mirar su evolución.',
           'grafico': os.path.abspath(png), 'detalle_csv': os.path.abspath(ruta)}
    if out_foco:
        out['foco'] = redondear(out_foco, 3)
    cm.salida(out)


# =========================================================== sensibilidad

def cmd_sensibilidad(a):
    import statsmodels.api as sm
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    df = cargar(a.datos)
    meta = meta_de(a.datos)
    exigir_campos(df, [a.y])
    a.x = a.x or []
    if a.x_propias:
        exigir_campos(df, a.x_propias)
    if not a.x and not a.x_propias:
        cm.salida({'error': 'Indicar --x (macro) y/o --x-propias (variables del propio banco)'}, 2)
    mac = pd.read_csv(a.macro, dtype={'periodo': str}).set_index('periodo') if a.macro else pd.DataFrame()
    faltan = [x.split(':')[0] for x in a.x if x.split(':')[0] not in mac]
    if faltan:
        cm.salida({'error': 'Variables macro que no están en el CSV: %s' % faltan}, 2)
    fecha = ultimo_con_dato(df, a.y.split(':')[0])
    ents = universo(df, a.entidades, fecha) + ['AAA00']
    xs = {}
    for x in a.x:
        s = a_mensual(pd.to_numeric(mac[x.split(':')[0]], errors='coerce'))
        xs[x] = transformar(s, x, a.transform).shift(a.rezago)
    maxlags = 12 if a.transform in ('auto', 'ia') else 3
    todas = list(a.x) + list(a.x_propias or [])
    filas, panel = [], []
    for cod in ents:
        s = serie(df, cod, a.y.split(':')[0])
        s = a_mensual(s)
        if s.dropna().empty:
            continue
        # Las series del banco se excluyen antes de transformar; las macro no (sus valores son genuinos)
        yt = transformar(excluir(s, a.excluir), a.y, a.transform)
        xs_ent = dict(xs)
        for x in (a.x_propias or []):
            sx = a_mensual(serie(df, cod, x.split(':')[0]))
            xs_ent[x] = transformar(excluir(sx, a.excluir), x, a.transform).shift(a.rezago)
        d = pd.concat([yt.rename('y')] + [xs_ent[x].rename(x) for x in xs_ent],
                      axis=1).dropna()
        if a.desde:
            d = d[d.index >= a.desde]
        if a.hasta:
            d = d[d.index <= a.hasta]
        if len(d) < a.min_obs:
            continue
        X = sm.add_constant(d[todas])
        try:
            r = sm.OLS(d['y'], X).fit(cov_type='HAC', cov_kwds={'maxlags': min(maxlags, len(d) // 4)})
        except Exception:  # noqa: BLE001
            continue
        ci = r.conf_int()
        fila = {'codigo': cod, 'entidad': nombre(df, cod), 'n': int(r.nobs), 'r2': float(r.rsquared)}
        for x in todas:
            fila['beta_' + x] = float(r.params[x])
            fila['p_' + x] = float(r.pvalues[x])
            fila['ic_' + x] = [float(ci.loc[x, 0]), float(ci.loc[x, 1])]
            sd_y = d['y'].std()
            fila['beta_std_' + x] = float(r.params[x] * d[x].std() / sd_y) if sd_y else np.nan
        filas.append(fila)
        if cod != 'AAA00':
            dd = d.copy()
            dd['codigo'] = cod
            panel.append(dd)
    if not filas:
        cm.salida({'error': 'Ninguna entidad con %d observaciones comunes' % a.min_obs,
                   'ayuda': 'Ampliar el panel en el tiempo o bajar --min-obs'}, 2)
    t = pd.DataFrame(filas)
    out_panel = None
    if panel:
        p = pd.concat(panel)
        dm = p.groupby('codigo')[['y'] + todas].transform(lambda s: s - s.mean())
        try:
            rp = sm.OLS(dm['y'], dm[todas]).fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(p['codigo'])[0]})
            cip = rp.conf_int()
            out_panel = {'entidades': int(p['codigo'].nunique()), 'n': int(rp.nobs),
                         'r2_within': float(rp.rsquared),
                         'coeficientes': {x: {'beta': float(rp.params[x]), 'p': float(rp.pvalues[x]),
                                              'ic95': [float(cip.loc[x, 0]), float(cip.loc[x, 1])]}
                                          for x in todas}}
            if len(todas) > 1:
                X = sm.add_constant(p[todas])
                out_panel['vif'] = {x: float(variance_inflation_factor(X.values, i + 1)) for i, x in enumerate(todas)}
        except Exception as e:  # noqa: BLE001
            out_panel = {'error': str(e)}
    x0 = todas[0]
    orden = t.sort_values('beta_' + x0, ascending=False)
    foco = resolver(df, a.foco) if a.foco else None
    filas_g = [(r['entidad'], r['beta_' + x0], r['ic_' + x0][0], r['ic_' + x0][1]) for _, r in orden.iterrows()]
    png = ruta_salida(a, 'sensibilidad_%s.png' % a.y.split(':')[0])
    gr.coeficientes(filas_g[:a.top], 'Sensibilidad de %s a %s' % (a.y, x0), png,
                    foco=nombre(df, foco) if foco else None,
                    fuente=fuente_txt(meta, 'OLS con errores HAC por entidad; %s; rezago %d meses.'
                                      % (a.transform, a.rezago)),
                    xlabel='Cambio en %s (%s) por unidad de cambio en %s (%s)'
                           % (a.y, etiqueta_tr(a.y, a.transform), x0, etiqueta_tr(x0, a.transform)))
    ruta = ruta_salida(a, 'sensibilidad_%s.csv' % a.y.split(':')[0])
    t.to_csv(ruta, index=False)
    sis = t[t['codigo'] == 'AAA00']
    out = {'y': a.y, 'x': a.x, 'x_propias': a.x_propias or [], 'transformacion': a.transform, 'rezago_meses': a.rezago,
           'ventana': '%s a %s' % (a.desde or 'inicio', a.hasta or 'fin'),
           'sistema': redondear(sis.to_dict('records')[0], 4) if len(sis) else None,
           'panel_efectos_fijos': redondear(out_panel, 4),
           'mas_sensibles': redondear(orden.head(5)[['entidad', 'n', 'r2', 'beta_' + x0, 'p_' + x0]].to_dict('records'), 3),
           'menos_sensibles': redondear(orden.tail(5)[['entidad', 'n', 'r2', 'beta_' + x0, 'p_' + x0]].to_dict('records'), 3),
           'como_leer': 'beta = cuánto cambia la métrica (transformada) por cada unidad de cambio de la '
                        'variable macro, con el rezago indicado. beta_std compara variables de distinta '
                        'escala. p > 0,10 o IC que cruza 0 = sin efecto distinguible. VIF > 5 = variables '
                        'macro redundantes entre sí (no leer cada beta por separado). Es asociación '
                        'condicionada, no causalidad; con pocos años de datos los betas cambian por régimen.',
           'grafico': os.path.abspath(png), 'detalle_csv': os.path.abspath(ruta)}
    if foco:
        ff = t[t['codigo'] == foco]
        out['foco'] = redondear(ff.to_dict('records')[0], 4) if len(ff) else 'sin observaciones suficientes'
    cm.salida(out)


# =========================================================== anomalías

def cmd_anomalias(a):
    df = cargar(a.datos)
    fecha = a.fecha or df.loc[df['tipo'] != 'grupo', 'periodo'].max()
    ents = universo(df, a.universo, fecha) + ['AAA00']
    campos = [c for c in (a.campos or ['irr_tot', 'irr_cons', 'irr_com', 'roe', 'spread', 'mix_pers',
                                       'cuota_bPr_priv', 'cuota_bDe_priv', 'cuota_bPers',
                                       'bPr_priv_ia', 'bDe_priv_ia', 'bPers_ia']) if c in df]
    filas = []
    ultimos = {}
    for c in campos:
        per = periodo_cercano(df, c, fecha)
        if not per:
            continue
        cambios = {}
        for cod in ents:
            s = a_mensual(serie(df, cod, c))
            if s.dropna().empty or per not in s.index:
                continue
            # Los *_ia ya son crecimientos: se evalúa el nivel del crecimiento, no su cambio
            ch = transformar(s, c, a.transform) if not c.endswith('_ia') else s
            ch = ch.dropna()
            if per not in ch.index or len(ch) < 6:
                continue
            ult = ch.loc[per]
            hist = ch[ch.index < per].tail(36)
            med = hist.median()
            mad = 1.4826 * (hist - med).abs().median()
            z_p = (ult - med) / mad if mad and mad > 0 else np.nan
            nivel = s.dropna()
            nivel = nivel[nivel.index <= per]
            rec, prev = nivel.tail(6), nivel.iloc[-18:-6] if len(nivel) >= 12 else nivel.iloc[:0]
            p_q = float(stats.ttest_ind(rec, prev, equal_var=False)[1]) if len(prev) >= 4 and len(rec) >= 3 else np.nan
            if cod != 'AAA00':  # el sistema se evalúa contra su historia, no es un par más
                cambios[cod] = ult
            filas.append({'codigo': cod, 'entidad': nombre(df, cod), 'campo': c, 'periodo': per,
                          'valor': float(s.loc[per]), 'cambio': float(ult),
                          'tipo_cambio': etiqueta_tr(c, a.transform) if not c.endswith('_ia') else 'crec. real 12m (%)',
                          'z_vs_historia': z_p, 'p_quiebre_nivel': p_q})
        ultimos[c] = cambios
    t = pd.DataFrame(filas)
    if t.empty:
        cm.salida({'error': 'Sin series suficientes (se necesitan ~18 meses de historia)'}, 2)
    zc = []
    for r in t.itertuples():
        vals = pd.Series(ultimos[r.campo])
        med = vals.median()
        mad = 1.4826 * (vals - med).abs().median()
        zc.append((r.cambio - med) / mad if mad and mad > 0 else np.nan)
    t['z_vs_pares'] = zc
    t['score'] = t[['z_vs_historia', 'z_vs_pares']].abs().max(axis=1)
    t = t.sort_values('score', ascending=False)
    ruta = ruta_salida(a, 'anomalias.csv')
    t.to_csv(ruta, index=False)
    def zt(v):
        return 's/d' if v != v else ('>10' if v > 10 else ('<-10' if v < -10 else gr.num(v, 1)))
    top = []
    for r in t.head(a.top).itertuples():
        zh, zp = r.z_vs_historia, r.z_vs_pares
        if zp == zp and abs(zp) >= 2:
            nat = 'idiosincrática: se despega de sus pares'
        elif zh == zh and abs(zh) >= 2:
            nat = 'sistémica: inusual para la entidad pero en línea con sus pares'
        else:
            nat = 'moderada'
        verbo = ('creció' if r.cambio > 0 else 'cayó') if r.campo.endswith('_ia') else \
                ('subió' if r.cambio > 0 else 'bajó')
        top.append({'entidad': r.entidad, 'campo': r.campo, 'periodo': r.periodo, 'valor': r.valor,
                    'cambio': r.cambio, 'tipo_cambio': r.tipo_cambio, 'z_vs_historia': zh,
                    'z_vs_pares': zp, 'p_quiebre_nivel': r.p_quiebre_nivel, 'naturaleza': nat,
                    'lectura': '%s: %s %s %s (%s); z %s vs su historia y %s vs pares'
                               % (gr.corto(r.entidad, 30), r.campo, verbo,
                                  gr.num(abs(r.cambio), 2), r.tipo_cambio, zt(zh), zt(zp))})
    cm.salida({'fecha': fecha, 'evaluadas': len(t), 'principales': redondear(top, 3),
               'como_leer': 'z robusto (mediana y MAD): |z| > 3 es raro, > 2 llamativo. Son señales para '
                            'investigar (¿error de carga, fusión, cambio de estrategia, shock?), no insights '
                            'en sí mismas. p_quiebre_nivel < 0,05: el nivel de los últimos 6 meses difiere '
                            'del de los 12 anteriores.',
               'detalle_csv': os.path.abspath(ruta)})


# =========================================================== gráficos

# =========================================================== novedades

NOV_SISTEMA = {
    'irr_tot': ('Mora total', 'alta'), 'irr_cons': ('Mora de consumo', 'alta'),
    'irr_com': ('Mora comercial', 'alta'), 'roe': ('ROE del sistema', 'baja'),
    'liq_amplia': ('Liquidez amplia', 'baja'), 'bPr_priv_ia': ('Crecimiento real de préstamos privados', None),
    'bDe_priv_ia': ('Crecimiento real de depósitos privados', None),
}


def cmd_novedades(a):
    """Lo más importante del mes, automático: récords, movimientos inusuales, bancos que más
    empeoraron, cambios de cuota y, si riesgo-bancario está instalado, sus alertas de cartera."""
    df = cargar(a.datos)
    fecha = a.fecha or df.loc[df['tipo'] != 'grupo', 'periodo'].max()
    hallazgos = []
    # 1. Sistema: récords de la serie y movimientos fuera de lo habitual
    for c, (etq, alerta) in NOV_SISTEMA.items():
        if c not in df:
            continue
        s = a_mensual(serie(df, 'AAA00', c)).dropna()
        s = s[s.index <= fecha]
        if fecha not in s.index or len(s) < 13:
            continue
        v = float(s.loc[fecha])
        if v >= s.max() or v <= s.min():
            alto = v >= s.max()
            hallazgos.append({'tipo': 'record', 'prioridad': 1 if alerta == ('alta' if alto else 'baja') else 2,
                              'lectura': '%s: %s %%, la más %s de la serie disponible (desde %s).%s' % (
                                  etq, gr.num(v, 2), 'alta' if alto else 'baja', s.index[0],
                                  ' Es una señal de alerta.' if alerta == ('alta' if alto else 'baja') else ''),
                              'datos': {'campo': c, 'valor': v, 'desde': s.index[0]}})
        if not c.endswith('_ia'):
            d = s.diff().dropna()
            if len(d) >= 13:
                hoy, hist = d.iloc[-1], d.iloc[-13:-1]
                sd = hist.std()
                if sd and sd > 0 and abs(hoy) >= 2 * sd and d.index[-1] == fecha:
                    hallazgos.append({'tipo': 'movimiento_inusual', 'prioridad': 2,
                                      'lectura': '%s %s %s puntos en el mes, %s veces lo habitual en los últimos 12 meses.' % (
                                          etq, 'subió' if hoy > 0 else 'bajó', gr.num(abs(hoy), 2),
                                          gr.num(abs(hoy) / sd, 1)),
                                      'datos': {'campo': c, 'cambio': float(hoy), 'desvio_12m': float(sd)}})
        else:
            hallazgos.append({'tipo': 'crecimiento_real', 'prioridad': 3,
                              'lectura': '%s: %s %% en 12 meses, descontada la inflación.' % (etq, gr.num(v, 1)),
                              'datos': {'campo': c, 'valor': v}})
    # 2. Entidades grandes: mora que más subió en 12 meses
    f = df[(df['periodo'] == fecha) & (df['tipo'] != 'grupo') & (df['tipo'] != 'historica')]
    sis_a = df.loc[(df['periodo'] == fecha) & (df['codigo'] == 'AAA00'), 'bA']
    tot = float(sis_a.iloc[0]) if len(sis_a) else f['bA'].sum()
    grandes = f[100 * f['bA'] / tot >= a.min_peso]['codigo'].tolist()
    hace12 = cm.mes_anterior(fecha, 12)
    if 'irr_tot' in df:
        cambios = []
        for c in grandes:
            s = serie(df, c, 'irr_tot')
            if fecha in s.index and hace12 in s.index and pd.notna(s[fecha]) and pd.notna(s[hace12]):
                cambios.append((float(s[fecha] - s[hace12]), c, float(s[fecha])))
        cambios.sort(reverse=True)
        if cambios:
            hallazgos.append({'tipo': 'mora_que_mas_subio', 'prioridad': 2,
                              'lectura': 'Entre las entidades con más de %s %% del sistema, la mora que más subió en 12 '
                                         'meses: %s.' % (gr.num(a.min_peso, 0), '; '.join(
                                             '%s (%s puntos, hoy %s %%)' % (gr.corto(nombre(df, c), 30), gr.num(dd, 2),
                                                                            gr.num(v, 2)) for dd, c, v in cambios[:a.top])),
                              'datos': [{'codigo': c, 'entidad': nombre(df, c), 'cambio_pp': dd, 'mora': v}
                                        for dd, c, v in cambios[:a.top]]})
    # 3. Cuotas: quién ganó y perdió más en 12 meses, avisando si fue un escalón
    for c, etq in (('cuota_bPr_priv', 'préstamos privados'), ('cuota_bDe_priv', 'depósitos privados')):
        if c not in df:
            continue
        movs = []
        for e in grandes:
            s = a_mensual(serie(df, e, c))
            s = s[(s.index >= hace12) & (s.index <= fecha)].dropna()
            if len(s) < 6 or s.index[0] != hace12 or s.index[-1] != fecha:
                continue
            total = float(s.iloc[-1] - s.iloc[0])
            paso = s.diff().abs()
            escalon = paso.idxmax() if abs(total) >= 0.5 and paso.max() >= 0.5 * abs(total) else None
            movs.append((total, e, escalon))
        if movs:
            movs.sort()
            sel = movs[-a.top:][::-1] + movs[:a.top]
            hallazgos.append({'tipo': 'cambio_de_cuota', 'prioridad': 3,
                              'lectura': 'Cuota de %s en 12 meses: %s.' % (etq, '; '.join(
                                  '%s %s%s puntos%s' % (gr.corto(nombre(df, e), 28), '+' if t > 0 else '', gr.num(t, 2),
                                                        ' (casi todo en %s: fusión, venta de cartera o escalón; '
                                                        'verificar antes de leerlo como tendencia)' % esc if esc else '') for t, e, esc in sel)),
                              'datos': [{'codigo': e, 'entidad': nombre(df, e), 'cambio_pp': t, 'escalon_en': esc}
                                        for t, e, esc in sel]})
    # 4. Alertas de cartera de riesgo-bancario, si está instalado
    r, _ = cm.ubicar_riesgo()
    riesgo = None
    if r:
        import subprocess
        p = subprocess.run([sys.executable, os.path.join(r['dir'], 'scripts', 'riesgo.py'), 'alertas', '--panel',
                            os.path.abspath(a.datos), '--fecha', fecha, '--top', str(a.top)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            riesgo = json.loads(p.stdout.decode('utf-8'))
        except ValueError:
            riesgo = {'error': p.stderr.decode('utf-8', 'replace')[-300:]}
        if riesgo.get('alertas'):
            hallazgos.append({'tipo': 'alertas_de_cartera', 'prioridad': 1,
                              'lectura': 'riesgo-bancario encontró %d alertas de cartera (%s). La más relevante: %s' % (
                                  riesgo['cantidad'], ', '.join('%s: %d' % kv for kv in riesgo['por_tipo'].items()),
                                  riesgo['alertas'][0]['lectura']),
                              'datos': riesgo['alertas'][:a.top]})
    hallazgos.sort(key=lambda h: h['prioridad'])
    cm.salida(redondear({
        'fecha': fecha, 'hallazgos': hallazgos,
        'riesgo_bancario': ('usado (%s)' % '.'.join(map(str, r['version']))) if r else
        'no instalado: sin alertas de cartera (%s)' % cm.RIESGO_URL,
        'error_riesgo': (riesgo or {}).get('error'),
        'como_leer': 'Hallazgos automáticos, ordenados por prioridad (1 = mirar primero). Un récord se mide '
                     'contra la historia que trae el panel. "Inusual" compara el cambio del mes con el desvío '
                     'de los últimos 12. Un cambio de cuota concentrado en un mes suele ser una fusión o un '
                     'escalón: verificarlo con "calidad" y "proforma" antes de leerlo como ganancia comercial. '
                     'Son puntos de partida para preguntar, no conclusiones.'}, 3))


def cmd_grafico(a):
    df = cargar(a.datos) if a.datos else None
    meta = meta_de(a.datos) if a.datos else {}
    if a.tipo == 'macro':
        mac = pd.read_csv(a.macro, dtype={'periodo': str}).set_index('periodo')
        series = {}
        for v in a.series:
            s = pd.to_numeric(mac[v], errors='coerce').dropna()
            if a.desde:
                s = s[s.index >= a.desde]
            if a.base100 and not s.empty:
                s = 100 * s / s.iloc[0]
            series[descripcion(v)[:40]] = s
        png = ruta_salida(a, a.archivo or 'macro.png')
        gr.linea(series, a.titulo or 'Variables macro' + (' (base %s = 100)' % a.desde if a.base100 else ''),
                 png, fuente='Fuente: BCRA, INDEC, datos.gob.ar.', dec=1)
        cm.salida({'grafico': os.path.abspath(png)})
    c = a.campo or a.y
    exigir_campos(df, [v for v in (a.campo, a.x, a.y, a.tamano) if v])
    if a.tipo == 'linea':
        ents = [resolver(df, e) for e in (a.entidades or ['sistema'])]
        foco = resolver(df, a.foco) if a.foco else (ents[0] if len(ents) > 1 else None)
        series = {}
        for e in ents:
            s = serie(df, e, c).dropna()
            if a.desde:
                s = s[s.index >= a.desde]
            series[nombre(df, e)] = s
        png = ruta_salida(a, a.archivo or 'linea_%s.png' % c)
        u = unidad(c)
        gr.linea(series, a.titulo or corta(c), png, foco=nombre(df, foco) if foco else None,
                 sufijo=' %' if u == '%' else '', dec=1, fuente=fuente_txt(meta),
                 subtitulo='%s [%s]' % (descripcion(c), u) if u else descripcion(c))
    elif a.tipo == 'dispersion':
        fecha = a.fecha or ultimo_con_dato(df, a.y)
        ents = universo(df, a.universo, fecha)
        meses = cm.meses_entre(cm.mes_anterior(fecha, max(1, a.ventana) - 1), fecha)
        d = df[df['codigo'].isin(ents) & df['periodo'].isin(meses)]
        cols = [v for v in dict.fromkeys([a.x, a.y, a.tamano or 'bA']) if v in df]
        g = d.groupby('codigo')[cols].mean().reset_index()
        g['entidad'] = g['codigo'].map(lambda k: nombre(df, k))
        if a.min_cuota and 'cuota_bA' in df:
            tam = d.groupby('codigo')['cuota_bA'].mean()
            g = g[g['codigo'].map(tam) >= a.min_cuota]
        png = ruta_salida(a, a.archivo or 'dispersion_%s_%s.png' % (a.x, a.y))
        foco = nombre(df, resolver(df, a.foco)) if a.foco else None
        gr.dispersion(g, a.x, a.y, a.titulo or '%s vs %s' % (corta(a.y), corta(a.x).lower()), png,
                      tamano=a.tamano or 'bA', foco=foco,
                      fuente=fuente_txt(meta, 'Promedio %s a %s.' % (meses[0], fecha)),
                      xlabel='%s [%s]' % (descripcion(a.x), unidad(a.x)),
                      ylabel='%s [%s]' % (descripcion(a.y), unidad(a.y)))
        rho, p = stats.spearmanr(g[a.x], g[a.y], nan_policy='omit')
        cm.salida({'grafico': os.path.abspath(png), 'entidades': len(g), 'rho_spearman': round(float(rho), 3),
                   'p': round(float(p), 4)})
    elif a.tipo == 'barras':
        fecha = periodo_cercano(df, c, a.fecha or df['periodo'].max())
        ents = universo(df, a.universo, fecha)
        d = df[(df['periodo'] == fecha) & df['codigo'].isin(ents)][['codigo', 'entidad', c]].dropna()
        d = d.sort_values(c, ascending=False).head(a.top)
        png = ruta_salida(a, a.archivo or 'barras_%s.png' % c)
        foco = nombre(df, resolver(df, a.foco)) if a.foco else None
        u = unidad(c)
        gr.barras_h(list(zip(d['entidad'], d[c])), a.titulo or '%s (%s)' % (corta(c), fecha), png,
                    foco=foco, sufijo=' %' if u == '%' else '', dec=1, fuente=fuente_txt(meta))
    cm.salida({'grafico': os.path.abspath(png)})


# =========================================================== CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def comun(p, datos=True):
        if datos:
            p.add_argument('--datos', required=True, help='CSV analítico (salida de preparar)')
        p.add_argument('--salida-dir', default='.', help='carpeta para CSV y PNG')

    p = sub.add_parser('preparar')
    p.add_argument('--panel', required=True)
    p.add_argument('--macro', help='CSV de macro_ar.py (con ipc) para pasar a pesos constantes')
    p.add_argument('--base', help='YYYY-MM de los pesos constantes (por defecto, último mes del panel)')
    p.add_argument('--salida', default='analitico.csv')

    p = sub.add_parser('proforma')
    p.add_argument('--panel', required=True, help='panel nominal de panel.py --historicas')
    p.add_argument('--fusion', nargs='+', required=True, help='ABSORBENTE=CODIGO_ABSORBIDA, ej. Galicia=150 Macro=259')
    p.add_argument('--salida', default='panel_pf.csv')

    p = sub.add_parser('rentabilidad')
    comun(p)
    p.add_argument('--foco')
    p.add_argument('--pares', nargs='+', default=['top10'])
    p.add_argument('--hasta', help='YYYY-MM (por defecto, último con resultados)')
    p.add_argument('--segmentos', help='segmentos.csv de "segmentar" para rentabilidad ponderada por segmento')

    p = sub.add_parser('calidad')
    comun(p)
    p.add_argument('--campos', nargs='+')
    p.add_argument('--umbral', type=float, default=1.8, help='múltiplo mes a mes que dispara alerta')
    p.add_argument('--umbral-pp', type=float, default=15.0)
    p.add_argument('--min-cuota', type=float, default=0.1, help='omitir entidades con menos de este %% del activo')
    p.add_argument('--salto-cuota', type=float, default=0.5, help='pp de cuota en un mes que disparan alerta')
    p.add_argument('--limpiar', help='CSV de salida con los picos aislados en blanco')

    p = sub.add_parser('cuotas')
    comun(p)
    p.add_argument('--campo', required=True, nargs='+',
                   help='un campo (detalle por entidad) o varios (mapa de cuotas por producto)')
    p.add_argument('--entidades', nargs='+', help='filas del mapa (por defecto, foco + 7 mayores)')
    p.add_argument('--desde')
    p.add_argument('--hasta')
    p.add_argument('--universo', default='bancos')
    p.add_argument('--foco')
    p.add_argument('--top', type=int, default=12)

    p = sub.add_parser('brechas')
    comun(p)
    p.add_argument('--foco', required=True)
    p.add_argument('--pares', nargs='+', default=['top10'],
                   help='bancos | privados | publicos | topN | lista de nombres')
    p.add_argument('--fecha')
    p.add_argument('--metricas', nargs='+')

    p = sub.add_parser('correlacion')
    comun(p)
    p.add_argument('--modo', choices=['temporal', 'transversal'], default='temporal')
    p.add_argument('--entidad', default='sistema')
    p.add_argument('--variables', nargs='+', required=True, help='campo o campo:transformación (ia|dif|var|mensual|nivel)')
    p.add_argument('--macro')
    p.add_argument('--macro-vars', nargs='+')
    p.add_argument('--transform', default='auto', choices=['auto', 'ia', 'dif', 'var', 'mensual', 'nivel'])
    p.add_argument('--rezagos', type=int, default=6)
    p.add_argument('--controles', nargs='+', help='variables macro a controlar (correlación parcial)')
    p.add_argument('--desde', help='YYYY-MM: inicio de la ventana (temporal; las variaciones usan meses previos)')
    p.add_argument('--hasta', help='YYYY-MM: fin de la ventana (temporal)')
    p.add_argument('--fecha')
    p.add_argument('--ventana', type=int, default=3, help='meses a promediar (transversal)')
    p.add_argument('--universo', default='bancos')
    p.add_argument('--min-cuota', type=float, default=0.05, help='cuota mínima de activo en %% (transversal)')
    p.add_argument('--excluir', nargs='+', help='rangos YYYY-MM:YYYY-MM a excluir (ej. 2020-04:2022-03, alivio COVID)')

    p = sub.add_parser('segmentar')
    comun(p)
    p.add_argument('--fecha')
    p.add_argument('--ventana', type=int, default=6)
    p.add_argument('--variables', nargs='+')
    p.add_argument('--resultados', nargs='+')
    p.add_argument('--universo', default='bancos')
    p.add_argument('--k', default='auto')
    p.add_argument('--min-cuota', type=float, default=0.05)
    p.add_argument('--foco')

    p = sub.add_parser('sensibilidad')
    comun(p)
    p.add_argument('--macro')
    p.add_argument('--y', required=True)
    p.add_argument('--x', nargs='+', help='variables macro (del CSV de macro_ar.py)')
    p.add_argument('--x-propias', nargs='+',
                   help='variables del propio banco como regresores (ej. bPers_ia:nivel = efecto cosecha)')
    p.add_argument('--entidades', nargs='+', default=['top20'])
    p.add_argument('--transform', default='auto', choices=['auto', 'ia', 'dif', 'var', 'mensual', 'nivel'])
    p.add_argument('--rezago', type=int, default=0)
    p.add_argument('--min-obs', type=int, default=18)
    p.add_argument('--desde', help='YYYY-MM: estimar solo desde este mes (comparar regímenes)')
    p.add_argument('--hasta')
    p.add_argument('--foco')
    p.add_argument('--top', type=int, default=25)
    p.add_argument('--excluir', nargs='+', help='rangos YYYY-MM:YYYY-MM a excluir (ej. 2020-04:2022-03, alivio COVID)')

    p = sub.add_parser('anomalias')
    comun(p)
    p.add_argument('--campos', nargs='+')
    p.add_argument('--fecha')
    p.add_argument('--universo', default='top20')
    p.add_argument('--transform', default='auto', choices=['auto', 'ia', 'mensual'])
    p.add_argument('--top', type=int, default=15)

    p = sub.add_parser('novedades')
    comun(p)
    p.add_argument('--fecha')
    p.add_argument('--min-peso', type=float, default=1.0, help='%% del activo del sistema para "entidades grandes"')
    p.add_argument('--top', type=int, default=3)

    p = sub.add_parser('grafico')
    p.add_argument('tipo', choices=['linea', 'dispersion', 'barras', 'macro'])
    p.add_argument('--datos')
    p.add_argument('--salida-dir', default='.')
    p.add_argument('--campo')
    p.add_argument('--entidades', nargs='+')
    p.add_argument('--foco')
    p.add_argument('--desde')
    p.add_argument('--x')
    p.add_argument('--y')
    p.add_argument('--tamano')
    p.add_argument('--fecha')
    p.add_argument('--ventana', type=int, default=1)
    p.add_argument('--universo', default='bancos')
    p.add_argument('--min-cuota', type=float, default=0.05)
    p.add_argument('--top', type=int, default=20)
    p.add_argument('--macro')
    p.add_argument('--series', nargs='+')
    p.add_argument('--base100', action='store_true')
    p.add_argument('--titulo')
    p.add_argument('--archivo')

    a = ap.parse_args()
    if getattr(a, 'pares', None) and len(a.pares) == 1:
        a.pares = a.pares[0]
    if getattr(a, 'universo', None) is not None and isinstance(a.universo, str):
        pass
    if getattr(a, 'entidades', None) and a.cmd == 'sensibilidad' and len(a.entidades) == 1:
        a.entidades = a.entidades[0]
    {'preparar': cmd_preparar, 'calidad': cmd_calidad, 'cuotas': cmd_cuotas, 'brechas': cmd_brechas,
     'correlacion': cmd_correlacion, 'segmentar': cmd_segmentar, 'sensibilidad': cmd_sensibilidad,
     'anomalias': cmd_anomalias, 'grafico': cmd_grafico, 'proforma': cmd_proforma,
     'rentabilidad': cmd_rentabilidad, 'novedades': cmd_novedades}[a.cmd](a)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        import traceback
        cm.salida({'error': '%s: %s' % (type(e).__name__, e), 'traza': traceback.format_exc()[-1500:]}, 1)
