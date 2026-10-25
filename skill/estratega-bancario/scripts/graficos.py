#!/usr/bin/env python3
"""
Estilo y gráficos estándar del Estratega Bancario (matplotlib, PNG).

Reglas que aplica: un solo eje Y (nunca doble eje), colores fijos por entidad
(el banco foco siempre en el primer color y el resto en gris cuando hay
muchos), grilla tenue, etiquetas directas selectivas, números con coma
decimal y fuente al pie. No se ejecuta solo: lo importa analizar.py.
"""
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
import numpy as np  # noqa: E402

SUPERFICIE = '#fcfcfb'
TEXTO = '#0b0b0b'
TEXTO_2 = '#52514e'
GRILLA = '#e6e5e0'
GRIS = '#b9b8b2'
# Orden categórico fijo (validado para daltonismo en pares adyacentes)
PALETA = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
DIVERGENTE = ['#184f95', '#3987e5', '#9ec5f4', '#f0efec', '#f2a7a6', '#e34948', '#a82a2a']
MARCADORES = ['o', 's', '^', 'D', 'v', 'P', 'X', '*']


def num(v, dec=1):
    """1234567.891 -> '1.234.567,9' (formato argentino)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return 's/d'
    s = '{:,.{d}f}'.format(v, d=dec)
    return s.replace(',', '_').replace('.', ',').replace('_', '.')


def estilo():
    plt.rcParams.update({
        'figure.facecolor': SUPERFICIE, 'axes.facecolor': SUPERFICIE,
        'savefig.facecolor': SUPERFICIE, 'axes.edgecolor': GRILLA,
        'axes.labelcolor': TEXTO_2, 'axes.titlecolor': TEXTO, 'xtick.color': TEXTO_2,
        'ytick.color': TEXTO_2, 'axes.grid': True, 'grid.color': GRILLA, 'grid.linewidth': 0.6,
        'grid.linestyle': '-', 'axes.spines.top': False, 'axes.spines.right': False,
        'axes.titlesize': 13, 'axes.titleweight': 'semibold', 'axes.titlelocation': 'left',
        'axes.labelsize': 10, 'xtick.labelsize': 9, 'ytick.labelsize': 9,
        'legend.fontsize': 9, 'legend.frameon': False, 'font.size': 10,
        'lines.linewidth': 2, 'axes.axisbelow': True,
    })


def formato_y(ax, dec=1, sufijo=''):
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, dec) + sufijo))


def formato_x(ax, dec=1, sufijo=''):
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, dec) + sufijo))


def corto(nombre, n=22):
    """Nombre de entidad abreviado para etiquetas."""
    s = str(nombre)
    for a, b in (('BANCO DE LA PROVINCIA DE ', 'BCO. PROV. '), ('BANCO DE LA NACION ARGENTINA', 'NACIÓN'),
                 ('BANCO DE LA CIUDAD DE BUENOS AIRES', 'CIUDAD'), ('BANCO DE GALICIA Y BUENOS AIRES', 'GALICIA'),
                 ('INDUSTRIAL AND COMMERCIAL BANK OF CHINA', 'ICBC'), ('BANCO ', ''), (' S.A.U.', ''),
                 (' S.A.', ''), (' SOCIEDAD ANONIMA', ''), (' SOCIEDAD ANÓNIMA', ''),
                 (' COMPAÑIA FINANCIERA', ' CF'), (' COMPAÑÍA FINANCIERA', ' CF'),
                 ('SISTEMA FINANCIERO (bancos y compañías financieras)', 'SISTEMA'),
                 ('10 PRIMEROS BANCOS PRIVADOS', 'TOP 10 PRIV.'), ('ENTIDADES PRIVADAS', 'PRIVADOS'),
                 ('ENTIDADES PÚBLICAS', 'PÚBLICOS')):
        s = s.replace(a, b)
    if s.isupper():
        s = ' '.join(SIGLAS.get(w, w) for w in s.strip().title().split())
    s = s.strip()
    return s if len(s) <= n else s[:n - 1] + '…'


SIGLAS = {'Bbva': 'BBVA', 'Icbc': 'ICBC', 'Bice': 'BICE', 'Bind': 'BIND', 'Hsbc': 'HSBC', 'Cmf': 'CMF',
          'Bst': 'BST', 'Bacs': 'BACS', 'Rci': 'RCI', 'Bnp': 'BNP', 'Jp': 'JP', 'Cf': 'CF',
          'N.A.': 'N.A.', 'Del': 'del', 'De': 'de', 'La': 'la', 'Y': 'y', 'Prov.': 'Prov.',
          'Bco.': 'Bco.', 'Top': 'Top', 'Priv.': 'Priv.'}


def colores(entidades, foco=None):
    """Color fijo por entidad: foco primero; más de 8 series -> foco en color y resto en gris."""
    orden = list(entidades)
    if foco in orden:
        orden.remove(foco)
        orden.insert(0, foco)
    if len(orden) > 8:
        return {e: (PALETA[0] if e == foco else GRIS) for e in orden}
    return {e: PALETA[i] for i, e in enumerate(orden)}


def titulo_(ax, texto, subtitulo=None):
    ax.set_title(texto, pad=24 if subtitulo else 10)
    if subtitulo:
        ax.text(0, 1.012, subtitulo, transform=ax.transAxes, fontsize=9, color=TEXTO_2, va='bottom')


def pie(fig, fuente):
    if fuente:
        import textwrap
        ancho = int(fig.get_figwidth() * 17)
        txt = '\n'.join(textwrap.wrap(fuente, ancho))
        fig.text(0.01, 0.01, txt, fontsize=8, color=TEXTO_2, ha='left', va='bottom')
        return txt.count('\n') + 1
    return 0


def guardar(fig, ruta, fuente=None):
    lineas = pie(fig, fuente)
    alto = fig.get_figheight()
    fig.tight_layout(rect=(0, (0.02 + 0.16 * lineas / alto) if lineas else 0, 1, 1))
    fig.savefig(ruta, dpi=160)
    plt.close(fig)
    return ruta


# ---------------------------------------------------------------- formas

def linea(series, titulo, ruta, foco=None, sufijo='', dec=1, fuente=None, subtitulo=None):
    """series: {nombre: pandas.Series indexada por 'YYYY-MM'}."""
    estilo()
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    cols = colores(series, foco)
    finales = []
    for nombre in sorted(series, key=lambda n: (n == foco, cols[n] != GRIS)):
        s = series[nombre].dropna()
        if s.empty:
            continue
        es_gris = cols[nombre] == GRIS
        ax.plot(s.index, s.values, color=cols[nombre], lw=1.2 if es_gris else 2,
                alpha=0.7 if es_gris else 1, zorder=1 if es_gris else 3,
                label=None if es_gris else corto(nombre))
        if not es_gris or nombre == foco:
            finales.append((s.index[-1], float(s.values[-1]), corto(nombre, 16), nombre == foco))
    etiquetas = sorted({p for s in series.values() for p in s.dropna().index})
    paso = max(1, len(etiquetas) // 10)
    ax.set_xticks(etiquetas[::paso])
    ax.tick_params(axis='x', rotation=45)
    ax.set_xlim(-0.5, len(etiquetas) - 0.5 + max(2, len(etiquetas) * 0.12))
    formato_y(ax, dec, sufijo)
    titulo_(ax, titulo, subtitulo)
    # Rótulos al final de cada línea, separados verticalmente para que no se pisen
    fig.canvas.draw()
    pos = sorted([(ax.transData.transform((etiquetas.index(x), y))[1], x, y, t, d)
                  for x, y, t, d in finales])
    minimo = 11 * fig.dpi / 72
    ys = []
    for py, *_ in pos:
        ys.append(max(py, ys[-1] + minimo) if ys else py)
    for (py, x, y, t, d), ny in zip(pos, ys):
        ax.annotate(t, (x, y), xytext=(6, (ny - py) * 72 / fig.dpi), textcoords='offset points',
                    fontsize=8, color=TEXTO, va='center', fontweight='semibold' if d else 'normal')
    if 2 <= len([c for c in cols.values() if c != GRIS]) and len(series) <= 8:
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.2), ncol=min(4, len(series)))
    return guardar(fig, ruta, fuente)


def barras_h(valores, titulo, ruta, foco=None, sufijo='', dec=1, fuente=None, xlabel=None):
    """valores: lista de (nombre, valor) ya ordenada."""
    estilo()
    alto = max(3.5, 0.32 * len(valores) + 1.2)
    fig, ax = plt.subplots(figsize=(9, alto))
    nombres = [corto(n, 28) for n, _ in valores]
    vals = [v for _, v in valores]
    col = [PALETA[0] if n == foco else (PALETA[1] if v < 0 else '#86b6ef') for n, v in valores]
    if foco is None:
        col = [PALETA[0] if v >= 0 else PALETA[1] for v in vals]
    y = np.arange(len(vals))
    ax.barh(y, vals, color=col, height=0.62)
    ax.set_yticks(y)
    ax.set_yticklabels(nombres)
    ax.invert_yaxis()
    ax.axvline(0, color=TEXTO_2, lw=0.8)
    ax.grid(axis='y', visible=False)
    rango = (max(vals + [0]) - min(vals + [0])) or 1
    ax.set_xlim(min(vals + [0]) - (0.18 * rango if min(vals) < 0 else 0),
                max(vals + [0]) + (0.18 * rango if max(vals) > 0 else 0))
    for yi, v in zip(y, vals):
        ax.text(v + (0.01 * rango if v >= 0 else -0.01 * rango), yi, num(v, dec) + sufijo,
                va='center', ha='left' if v >= 0 else 'right', fontsize=8, color=TEXTO)
    formato_x(ax, dec, sufijo)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.set_title(titulo)
    return guardar(fig, ruta, fuente)


def dispersion(df, x, y, titulo, ruta, etiqueta='entidad', tamano=None, foco=None, color=None,
               fuente=None, xlabel=None, ylabel=None, n_etiquetas=12):
    """Cuadrante con líneas en las medianas. df: DataFrame con columnas x, y, etiqueta."""
    estilo()
    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    d = df.dropna(subset=[x, y]).copy()
    if tamano and tamano in d:
        t = d[tamano].clip(lower=0).fillna(0)
        s = 30 + 900 * (t / t.max()) if t.max() > 0 else 60
    else:
        s = 60
    if color and color in d:
        grupos = sorted(d[color].dropna().unique())
        for i, g in enumerate(grupos):
            m = d[color] == g
            ax.scatter(d.loc[m, x], d.loc[m, y], s=s[m] if hasattr(s, '__getitem__') else s,
                       color=PALETA[i % 8], marker=MARCADORES[i % 8], alpha=0.75,
                       edgecolor=SUPERFICIE, linewidth=1.5, label=str(g), zorder=3)
        leg = ax.legend(loc='best', title=color)
        for h in getattr(leg, 'legend_handles', getattr(leg, 'legendHandles', [])):
            h.set_sizes([60])
    else:
        cols = [PALETA[0] if (foco is not None and e == foco) else '#86b6ef' for e in d[etiqueta]]
        ax.scatter(d[x], d[y], s=s, color=cols, alpha=0.8, edgecolor=SUPERFICIE, linewidth=1.5,
                   zorder=3)
    ax.axvline(d[x].median(), color=GRIS, lw=1)
    ax.axhline(d[y].median(), color=GRIS, lw=1)
    orden = d.sort_values(tamano, ascending=False) if tamano and tamano in d else d
    rotular = list(orden[etiqueta].head(n_etiquetas))
    if foco is not None and foco not in rotular:
        rotular.insert(0, foco)
    elif foco is not None:
        rotular.remove(foco)
        rotular.insert(0, foco)
    ax.set_xlabel(xlabel or x)
    ax.set_ylabel(ylabel or y)
    formato_x(ax)
    formato_y(ax)
    rotular_sin_choques(fig, ax, [(r[x], r[y], corto(r[etiqueta], 18), r[etiqueta] == foco)
                                  for _, r in d.drop_duplicates(etiqueta).set_index(etiqueta, drop=False)
                                  .reindex(rotular).dropna(subset=[x, y]).iterrows()])
    titulo_(ax, titulo, 'Líneas grises: medianas. Tamaño del punto: %s' %
            ({'bA': 'activo', 'bPr_priv': 'préstamos privados', 'bDe_priv': 'depósitos privados'}.get(tamano, tamano)
             if tamano else 'uniforme'))
    return guardar(fig, ruta, fuente)


def rotular_sin_choques(fig, ax, puntos):
    """Etiquetas de puntos evitando superposiciones (búsqueda simple de posiciones libres).

    puntos: [(x, y, texto, destacado)] en orden de prioridad."""
    fig.canvas.draw()
    esc = fig.dpi / 72.0
    ocupados = []
    cand = [(6, 4), (6, -12), (-6, 4), (-6, -12), (6, 16), (-6, 16), (6, -24), (-6, -24),
            (14, 28), (-14, 28), (14, -36), (-14, -36)]
    for px, py, txt, dest in puntos:
        X, Y = ax.transData.transform((px, py))
        w, h = 4.6 * len(txt) * esc, 10 * esc
        elegido = None
        for dx, dy in cand:
            x0 = X + dx * esc if dx >= 0 else X + dx * esc - w
            caja = (x0, Y + dy * esc, x0 + w, Y + dy * esc + h)
            if not any(caja[0] < c[2] and caja[2] > c[0] and caja[1] < c[3] and caja[3] > c[1]
                       for c in ocupados):
                elegido = (dx, dy, caja)
                break
        if elegido is None:
            continue  # sin lugar: el punto queda sin rótulo (el CSV tiene el detalle)
        dx, dy, caja = elegido
        ocupados.append(caja)
        ax.annotate(txt, (px, py), xytext=(dx, dy), textcoords='offset points', fontsize=8,
                    color=TEXTO, ha='left' if dx >= 0 else 'right',
                    fontweight='semibold' if dest else 'normal',
                    arrowprops=dict(arrowstyle='-', color=GRIS, lw=0.6) if abs(dy) > 16 else None)


def heatmap(matriz, filas, columnas, titulo, ruta, anotaciones=None, fuente=None, vmax=1.0,
            positivo_azul=False):
    """Matriz con escala divergente azul-gris-rojo (centro = 0). positivo_azul invierte los polos
    (para cambios de cuota: ganar = azul, perder = rojo)."""
    from matplotlib.colors import LinearSegmentedColormap
    estilo()
    cmap = LinearSegmentedColormap.from_list('div', DIVERGENTE[::-1] if positivo_azul else DIVERGENTE)
    fig, ax = plt.subplots(figsize=(1.1 * len(columnas) + 3.5, 0.55 * len(filas) + 2.2))
    m = np.array(matriz, dtype=float)
    im = ax.imshow(m, cmap=cmap, vmin=-vmax, vmax=vmax, aspect='auto')
    ax.set_xticks(range(len(columnas)))
    ax.set_xticklabels(columnas, rotation=40, ha='right')
    ax.set_yticks(range(len(filas)))
    ax.set_yticklabels(filas)
    ax.grid(False)
    for i in range(len(filas)):
        for j in range(len(columnas)):
            if np.isnan(m[i, j]):
                continue
            txt = num(m[i, j], 2) if anotaciones is None else anotaciones[i][j]
            ax.text(j, i, txt, ha='center', va='center', fontsize=8,
                    color=SUPERFICIE if abs(m[i, j]) > 0.6 * vmax else TEXTO)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.outline.set_visible(False)
    ax.set_title(titulo)
    return guardar(fig, ruta, fuente)


def benchmark(filas, titulo, ruta, foco_nombre, fuente=None, textos=None):
    """filas: [(metrica, p25, mediana, p75, percentil_foco, mejor_es_mayor|None)] en percentiles 0-100.
    textos: lista opcional de rótulos a la derecha (p. ej. 'foco 18,4 · med. 11,4').

    Dibuja, por métrica, el rango intercuartil de los pares, la mediana y el banco foco,
    todo en escala de percentil para que métricas de distinta unidad compartan un eje.
    """
    estilo()
    fig, ax = plt.subplots(figsize=(11 if textos else 9.5, 0.42 * len(filas) + 1.8))
    y = np.arange(len(filas))
    if textos:
        for yi, t in zip(y, textos):
            ax.text(104, yi, t, va='center', ha='left', fontsize=8, color=TEXTO_2, clip_on=False)
    for yi, (met, p25, med, p75, val, mejor) in zip(y, filas):
        ax.plot([25, 75], [yi, yi], color='#cde2fb', lw=8, solid_capstyle='round', zorder=1)
        ax.plot([50], [yi], marker='|', color=TEXTO_2, ms=14, mew=2, zorder=2)
        if val is not None and not np.isnan(val):
            c = PALETA[0]
            if mejor is True and val < 25 or mejor is False and val > 75:
                c = PALETA[1]
            ax.plot([val], [yi], 'o', color=c, ms=8, mec=SUPERFICIE, mew=1.5, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([f[0] for f in filas])
    ax.invert_yaxis()
    ax.set_xlim(-2, 102)
    ax.set_xlabel('Percentil entre pares (0 = menor valor, 100 = mayor)')
    ax.grid(axis='y', visible=False)
    titulo_(ax, titulo, 'Banda: pares p25-p75 · trazo: mediana · punto: %s (naranja = debilidad)%s' %
            (corto(foco_nombre), ' · a la derecha: valor del foco y mediana' if textos else ''))
    return guardar(fig, ruta, fuente)


def coeficientes(filas, titulo, ruta, foco=None, fuente=None, xlabel='Coeficiente'):
    """filas: [(nombre, beta, ic_bajo, ic_alto)] ya ordenadas."""
    estilo()
    fig, ax = plt.subplots(figsize=(9, 0.32 * len(filas) + 1.6))
    y = np.arange(len(filas))
    for yi, (n, b, lo, hi) in zip(y, filas):
        c = PALETA[0] if n == foco else ('#86b6ef' if foco else PALETA[0])
        ax.plot([lo, hi], [yi, yi], color=c, lw=2, zorder=2)
        ax.plot([b], [yi], 'o', color=c, ms=7, mec=SUPERFICIE, mew=1.5, zorder=3)
    ax.axvline(0, color=TEXTO_2, lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels([corto(f[0], 26) for f in filas])
    ax.invert_yaxis()
    ax.grid(axis='y', visible=False)
    ax.set_xlabel(xlabel)
    formato_x(ax, 2)
    titulo_(ax, titulo, 'Punto: coeficiente · línea: intervalo de confianza 95 %')
    return guardar(fig, ruta, fuente)
