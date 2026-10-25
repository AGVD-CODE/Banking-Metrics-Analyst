#!/usr/bin/env python3
"""
Funciones compartidas por los scripts del Oráculo BCRA.

Copia incluida en estratega-bancario, tomada del skill bcra-oraculo
(https://github.com/AGVD-CODE/BCRA-Oracle, mismo autor, licencia MIT), versión de
octubre de 2026. Se incluye para que el skill sea autocontenido. Para usar otra
copia (por ejemplo, una versión más nueva de bcra-oraculo), definir la variable
de entorno BCRA_ORACULO_DIR con la carpeta de ese skill.

Solo usa la biblioteca estándar de Python 3.8+: no hace falta instalar nada.
Los demás scripts lo importan; no se ejecuta solo.

Fuentes:
- API JSON del sitio del BCRA (la que usan las páginas "Información de Entidades
  Financieras" de www.bcra.gob.ar). Rápida: ~1 s y pocos KB por consulta.
- PDF mensual "Información de Entidades Financieras" (solo para series históricas
  y para la ficha institucional: directivos, accionistas, auditor). Requiere
  pdftotext (paquete poppler-utils).
"""
import concurrent.futures as cf
import decimal
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

BCRA = 'https://www.bcra.gob.ar'
API = BCRA + '/api/endpoints/'
PDF_ENTIDADES = BCRA + '/archivos/Pdfs/PublicacionesEstadisticas/Entidades/{ym}e.pdf'
UA = 'Mozilla/5.0 (compatible; bcra-oraculo/2.0; +https://github.com/agvd-code/BCRA-Oracle)'

CACHE_DIR = os.path.join(tempfile.gettempdir(), 'bcra-oraculo-cache')
# Caché de sesión: evita repetir descargas idénticas dentro de la misma
# conversación. Las fuentes se actualizan una vez por mes.
CACHE_TTL = int(os.environ.get('BCRA_ORACULO_TTL', '7200'))
SIN_CACHE = os.environ.get('BCRA_ORACULO_SIN_CACHE') == '1'
TIMEOUT = 45
WORKERS = 16

DOMINIOS = 'www.bcra.gob.ar, www.indec.gob.ar'
AYUDA_RED = ('El entorno no llega a las fuentes oficiales. Pedir al usuario que habilite '
             'el acceso de red a ' + DOMINIOS + ' en la configuración de ejecución de '
             'código de su entorno, o que descargue el archivo y lo suba.')

MESES = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7,
         'ago': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12}
MESES_NOMBRE = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
                'noviembre': 11, 'diciembre': 12}


class ErrorFuente(Exception):
    """La fuente respondió algo inesperado o no tiene el dato."""


class NoEncontrado(ErrorFuente):
    """HTTP 404: el archivo todavía no se publicó (o cambió la URL)."""


class SinRed(Exception):
    """No hay conexión con la fuente (DNS, proxy o firewall)."""


class Ambiguo(ErrorFuente):
    """El nombre no identifica una sola entidad. Lleva los candidatos en .datos."""

    def __init__(self, mensaje, datos):
        ErrorFuente.__init__(self, mensaje)
        self.datos = datos


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------

def sin_acentos(s):
    return unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()


def norm(s):
    """Mayúsculas, sin acentos ni signos, espacios simples."""
    s = re.sub(r'[^A-Z0-9]+', ' ', sin_acentos(s).upper())
    return re.sub(r'\s+', ' ', s).strip()


def clave(s):
    """Como norm() pero sin espacios: 'A C T I V O' y 'Activo' dan 'ACTIVO'."""
    return norm(s).replace(' ', '')


def periodo_iso(texto):
    """'Dic-2024', 'Set-2025', 'julio de 2026' -> '2024-12', '2025-09', '2026-07'."""
    t = sin_acentos(texto).strip().lower()
    m = re.match(r'([a-z]{3})[a-z]*[-\s/]+(?:de\s+)?(\d{4})', t)
    if m and m.group(1) in MESES:
        return '%s-%02d' % (m.group(2), MESES[m.group(1)])
    m = re.match(r'(\d{4})-?(\d{2})$', t)
    if m:
        return '%s-%s' % (m.group(1), m.group(2))
    return None


def mes_anterior(ym, n=1):
    a, m = int(ym[:4]), int(ym[5:7])
    m -= n
    while m < 1:
        m += 12
        a -= 1
    return '%04d-%02d' % (a, m)


def num_ar(s):
    """'1.234,5' -> 1234.5 ; '12,3%' -> 12.3 ; '---' -> None."""
    s = str(s).strip().rstrip('%').strip()
    if s in ('', '---', '-', 'NA', 's/d'):
        return None
    try:
        return float(s.replace('.', '').replace(',', '.'))
    except ValueError:
        return None


def salida(obj, codigo=0):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=1, default=str) + '\n')
    sys.stdout.flush()
    if codigo:
        sys.exit(codigo)


def ejecutar(main):
    """Corre main() y convierte los errores en JSON legible (nunca un traceback)."""
    try:
        main()
    except SinRed as e:
        salida({'error': 'Sin acceso a la fuente oficial', 'detalle': str(e),
                'sin_acceso_red': True, 'ayuda': AYUDA_RED}, 2)
    except Ambiguo as e:
        d = {'error': str(e)}
        d.update(e.datos)
        salida(d, 1)
    except ErrorFuente as e:
        salida({'error': str(e)}, 1)
    except KeyboardInterrupt:
        salida({'error': 'Interrumpido'}, 130)


# ---------------------------------------------------------------------------
# HTTP con reintentos y caché de sesión
# ---------------------------------------------------------------------------

def _ruta_cache(url):
    return os.path.join(CACHE_DIR, hashlib.sha1(url.encode('utf-8')).hexdigest())


def descargar(url, ttl=None, timeout=TIMEOUT, intentos=3, validar=None):
    """GET que devuelve bytes. Reintenta errores transitorios y guarda en caché.

    validar: función(bytes) -> bool. Si devuelve False, se considera que el
    archivo no está publicado (p. ej. una página HTML en lugar de un PDF).
    """
    ttl = CACHE_TTL if ttl is None else ttl
    ruta = _ruta_cache(url)
    if not SIN_CACHE and ttl > 0 and os.path.exists(ruta):
        if time.time() - os.path.getmtime(ruta) < ttl:
            with open(ruta, 'rb') as f:
                return f.read()
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                datos = r.read()
            if validar is not None and not validar(datos):
                raise NoEncontrado('No publicado (contenido inválido): ' + url)
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                tmp = ruta + '.%d.%d.tmp' % (os.getpid(), threading.get_ident())
                with open(tmp, 'wb') as f:
                    f.write(datos)
                os.replace(tmp, ruta)
            except OSError:
                pass  # sin caché si el disco no deja escribir
            return datos
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NoEncontrado('No publicado (HTTP 404): ' + url)
            ultimo = e
            if e.code in (403, 407) and _es_proxy(e):
                raise SinRed('%s (%s)' % (e, url))
            if e.code < 500 and e.code != 429:
                break
        except urllib.error.URLError as e:
            ultimo = e
            texto = str(e.reason)
            if any(x in texto for x in ('Name or service not known', 'getaddrinfo',
                                         'nodename nor servname', 'Temporary failure in name',
                                         'Tunnel connection failed', 'Network is unreachable')):
                raise SinRed('%s (%s)' % (texto, url))
        except (TimeoutError, ConnectionError, OSError) as e:
            ultimo = e
        time.sleep(0.6 * (2 ** i))
    if isinstance(ultimo, urllib.error.URLError) and not isinstance(ultimo, urllib.error.HTTPError):
        raise SinRed('%s (%s)' % (ultimo.reason, url))
    raise ErrorFuente('No se pudo descargar %s: %s' % (url, ultimo))


def _es_proxy(e):
    try:
        return 'proxy' in str(e.headers).lower() or e.code == 407
    except Exception:
        return False


def api(endpoint, **params):
    """Llama a la API JSON del sitio del BCRA y devuelve el dict."""
    url = API + endpoint + '?' + urllib.parse.urlencode(params)
    datos = descargar(url)
    try:
        d = json.loads(datos.decode('utf-8'))
    except ValueError:
        # No dejar en caché una respuesta corrupta
        try:
            os.remove(_ruta_cache(url))
        except OSError:
            pass
        raise ErrorFuente('Respuesta no JSON del BCRA para ' + url)
    if isinstance(d, dict) and d.get('success') is False:
        raise ErrorFuente('El BCRA respondió error para %s: %s' % (url, d.get('error')))
    return d


def en_paralelo(funcion, elementos, workers=WORKERS):
    """Aplica funcion a cada elemento en paralelo. Devuelve [(elemento, resultado|Exception)]."""
    elementos = list(elementos)
    out = [None] * len(elementos)
    with cf.ThreadPoolExecutor(max_workers=min(workers, max(1, len(elementos)))) as ex:
        futs = {ex.submit(funcion, e): i for i, e in enumerate(elementos)}
        for f in cf.as_completed(futs):
            i = futs[f]
            try:
                out[i] = (elementos[i], f.result())
            except Exception as e:  # se informa por elemento
                out[i] = (elementos[i], e)
    for _, r in out:
        if isinstance(r, SinRed):
            raise r
    return out


# ---------------------------------------------------------------------------
# Entidades: nómina, grupos y resolución de nombres
# ---------------------------------------------------------------------------

GRUPOS = {
    'sistema': ('AAA00', 'SISTEMA FINANCIERO (bancos y compañías financieras)'),
    'publicos': ('AAA10', 'ENTIDADES PÚBLICAS'),
    'privados': ('AAA20', 'ENTIDADES PRIVADAS'),
    'companias': ('AAA30', 'COMPAÑÍAS FINANCIERAS'),
    'top10': ('AAA50', '10 PRIMEROS BANCOS PRIVADOS'),
}
ALIAS_GRUPO = {
    'SISTEMA': 'sistema', 'SISTEMA FINANCIERO': 'sistema', 'TOTAL': 'sistema',
    'TOTAL DEL SISTEMA': 'sistema', 'TODO EL SISTEMA': 'sistema', 'AAA00': 'sistema',
    'PUBLICOS': 'publicos', 'BANCOS PUBLICOS': 'publicos', 'ENTIDADES PUBLICAS': 'publicos',
    'PUBLICAS': 'publicos', 'AAA10': 'publicos',
    'PRIVADOS': 'privados', 'BANCOS PRIVADOS': 'privados', 'ENTIDADES PRIVADAS': 'privados',
    'PRIVADAS': 'privados', 'AAA20': 'privados',
    'COMPANIAS': 'companias', 'COMPANIAS FINANCIERAS': 'companias', 'AAA30': 'companias',
    'TOP10': 'top10', 'TOP 10': 'top10', '10 PRIMEROS': 'top10',
    '10 PRIMEROS BANCOS PRIVADOS': 'top10', 'DIEZ PRIMEROS': 'top10', 'AAA50': 'top10',
}

# Nombres coloquiales -> código BCRA. Se verifican contra la nómina vigente.
ALIAS = {
    'GALICIA': 7, 'NACION': 11, 'BNA': 11, 'BANCO NACION': 11, 'PROVINCIA': 14,
    'BANCO PROVINCIA': 14, 'BAPRO': 14, 'PROVINCIA DE BUENOS AIRES': 14, 'ICBC': 15,
    'CITI': 16, 'CITIBANK': 16, 'BBVA': 17, 'FRANCES': 17, 'BBVA FRANCES': 17,
    'BANCOR': 20, 'CORDOBA': 20, 'PROVINCIA DE CORDOBA': 20, 'SUPERVIELLE': 27,
    'CIUDAD': 29, 'BANCO CIUDAD': 29, 'PATAGONIA': 34, 'HIPOTECARIO': 44,
    'SAN JUAN': 45, 'MUNICIPAL': 65, 'MUNICIPAL DE ROSARIO': 65, 'SANTANDER': 72,
    'SANTANDER RIO': 72, 'CHUBUT': 83, 'SANTA CRUZ': 86, 'LA PAMPA': 93, 'PAMPA': 93,
    'CORRIENTES': 94, 'NEUQUEN': 97, 'BPN': 97, 'BANK OF CHINA': 131, 'BRUBANK': 143,
    'BIBANK': 147, 'JP MORGAN': 165, 'JPMORGAN': 165, 'CREDICOOP': 191, 'VALORES': 198,
    'ROELA': 247, 'MARIVA': 254, 'BNP': 266, 'BNP PARIBAS': 266, 'TIERRA DEL FUEGO': 268,
    'BROU': 269, 'REPUBLICA ORIENTAL DEL URUGUAY': 269, 'SAENZ': 277, 'MERIDIAN': 281,
    'MACRO': 285, 'COMAFI': 299, 'BICE': 300, 'PIANO': 301, 'JULIO': 305, 'RIOJA': 309,
    'DEL SOL': 310, 'CHACO': 311, 'VOII': 312, 'FORMOSA': 315, 'CMF': 319,
    'SANTIAGO DEL ESTERO': 321, 'INDUSTRIAL': 322, 'BIND': 322, 'SANTA FE': 330,
    'CETELEM': 331, 'CARREFOUR': 332, 'SERVICIOS FINANCIEROS': 332, 'BST': 338,
    'RCI': 339, 'BACS': 340, 'MASVENTAS': 341, 'UALA': 384, 'ENTRE RIOS': 386,
    'COLUMBIA': 389, 'BICA': 426, 'COINAG': 431, 'COMERCIO': 432, 'SUCREDITO': 435,
    'DINO': 448, 'NARANJA': 45030, 'NARANJA X': 45030, 'NARANJA DIGITAL': 45030,
    'REBA': 45072, 'MONTEMAR': 45056, 'TOYOTA': 44099, 'VOLKSWAGEN': 44088,
    'JOHN DEERE': 44096, 'MERCEDES BENZ': 44094, 'ROMBO': 44095, 'FCA': 44092,
    'PSA': 44098, 'GPAT': 44093, 'CREDITO REGIONAL': 65203,
}
VACIAS = {'BANCO', 'BANK', 'DE', 'LA', 'DEL', 'EL', 'LOS', 'Y', 'S', 'A', 'U', 'SA', 'SAU',
          'SOCIEDAD', 'ANONIMA', 'UNIPERSONAL', 'NUEVO', 'COMPANIA', 'FINANCIERA', 'ARGENTINA'}


def codigo_api(codigo):
    """7 -> '00007' ; 'AAA00' -> 'AAA00'."""
    s = str(codigo).strip().upper()
    return s if s.startswith('AAA') else '%05d' % int(s)


def nomina(grupo='AAA00'):
    """Lista de entidades vigentes de un grupo: [{'codigo': 7, 'nombre': '...'}]."""
    d = api('nomina-entidades.php', action='nomina_' + grupo, lang='es')
    if d.get('inhabilitado'):
        raise ErrorFuente('La consulta de nómina del BCRA está en mantenimiento')
    return [{'codigo': int(e['codigo']), 'nombre': e['denominacion'].strip()}
            for e in (d.get('entidades') or [])]


def _tokens(s):
    return [t for t in norm(s).split() if t not in VACIAS]


def resolver(consulta, entidades=None):
    """Resuelve nombre, alias, código o grupo.

    Devuelve dict {'codigo', 'api', 'nombre', 'tipo': 'entidad'|'grupo'} o lanza
    ErrorFuente con candidatos (ambigüedad) o sugerencias (no encontrado).
    """
    q = str(consulta).strip()
    nq = norm(q)
    if nq in ALIAS_GRUPO:
        g = ALIAS_GRUPO[nq]
        cod, nombre = GRUPOS[g]
        return {'codigo': cod, 'api': cod, 'nombre': nombre, 'tipo': 'grupo', 'grupo': g}
    entidades = entidades if entidades is not None else nomina()
    por_codigo = {e['codigo']: e for e in entidades}
    if re.fullmatch(r'\d{1,5}', q):
        e = por_codigo.get(int(q))
        if not e:
            raise ErrorFuente('No hay una entidad vigente con código %s en la nómina del BCRA' % q)
        return _ent(e)
    nq_sin_banco = re.sub(r'^(BANCO|BCO)\s+', '', nq)
    for k in (nq, nq_sin_banco):
        if k in ALIAS and ALIAS[k] in por_codigo:
            return _ent(por_codigo[ALIAS[k]])
    # Coincidencia exacta del nombre normalizado
    exactos = [e for e in entidades if norm(e['nombre']) == nq]
    if len(exactos) == 1:
        return _ent(exactos[0])
    # Todas las palabras significativas presentes en el nombre
    tq = _tokens(q) or nq.split()
    cands = [e for e in entidades if all(any(t == w or (len(t) >= 4 and w.startswith(t))
                                             for w in norm(e['nombre']).split()) for t in tq)]
    if len(cands) == 1:
        return _ent(cands[0])
    if len(cands) > 1:
        raise Ambiguo('"%s" coincide con varias entidades: preguntar al usuario cuál' % q,
                      {'candidatos': [{'codigo': e['codigo'], 'nombre': e['nombre']}
                                      for e in cands]})
    nombres = {norm(e['nombre']): e for e in entidades}
    sug = difflib.get_close_matches(nq, list(nombres), n=5, cutoff=0.4)
    raise Ambiguo('"%s" no figura en la nómina de %d entidades financieras vigentes del BCRA '
                  '(bancos y compañías financieras; billeteras y otros proveedores de pago '
                  'no están incluidos)' % (q, len(entidades)),
                  {'sugerencias_por_parecido': [{'codigo': nombres[x]['codigo'],
                                                 'nombre': nombres[x]['nombre']} for x in sug]})


def _ent(e):
    return {'codigo': e['codigo'], 'api': codigo_api(e['codigo']), 'nombre': e['nombre'],
            'tipo': 'entidad'}


# ---------------------------------------------------------------------------
# Catálogo de campos (claves estables usadas por todos los scripts)
# ---------------------------------------------------------------------------
# clave: (sección, descripción, unidad, aditivo)
# "aditivo" = se puede sumar entre entidades (sirve para calcular participación).

CAMPOS = {}


def _c(seccion, unidad, aditivo, pares):
    for k, desc in pares:
        CAMPOS[k] = (seccion, desc, unidad, aditivo)


# Indicadores (mensual). Clave por código oficial del indicador.
IND_CODIGOS = {
    'C1': 'apalancamiento', 'C2': 'perdida_s2a5', 'C3': 'perdida_s3a5',
    'A9': 'irr_tot', 'A11': 'irr_priv', 'A12': 'part_com', 'A13': 'part_cons',
    'A14': 'prev_irr', 'A16': 'irr_cons', 'A17': 'irr_com', 'A21': 'exc_prev',
    'AG3': 'part_venc', 'AG29': 'efectivo_activo',
    'E1': 'absorc_gastos', 'E2': 'margen_rent_gastos', 'E4': 'dep_empleado',
    'E5': 'fin_empleado',
    'R1': 'roe', 'R2': 'roe_ord', 'R8': 'tasa_prest', 'R9': 'tasa_dep', 'R17': 'gpers_gadm',
    'RG1': 'roa', 'RG2_II': 'margen_fin_activo', 'RG3': 'roa_inco',
    'RG4_II': 'result_serv_activo', 'RG5': 'roa_adm', 'RG15': 'roa_aig',
    'L1': 'liq_amplia', 'L8_II': 'liq_tit_cot', 'L9': 'liq_bcra',
}
_c('indicadores', 'veces', False, [('apalancamiento', 'Apalancamiento: activo / patrimonio neto (C1)')])
_c('indicadores', '%', False, [
    ('perdida_s2a5', 'Pérdida potencial de cartera en situación 2 a 5 (C2)'),
    ('perdida_s3a5', 'Pérdida potencial de cartera en situación 3 a 5 (C3)'),
    ('irr_tot', 'Mora total: cartera irregular / financiaciones totales (A9)'),
    ('irr_priv', 'Cartera irregular del sector privado (A11)'),
    ('part_com', 'Participación de la cartera comercial en el sector privado (A12)'),
    ('part_cons', 'Participación de la cartera de consumo en el sector privado (A13)'),
    ('prev_irr', 'Cobertura: previsiones / cartera irregular total (A14)'),
    ('irr_cons', 'Mora de consumo: cartera irregular consumo sector privado (A16)'),
    ('irr_com', 'Mora comercial: cartera irregular comercial sector privado (A17)'),
    ('exc_prev', 'Posición de previsiones mínimas sector privado no financiero (A21)'),
    ('part_venc', 'Importancia de la cartera vencida del sector privado (AG3)'),
    ('efectivo_activo', 'Efectivo y depósitos en bancos / activo (AG29)'),
    ('absorc_gastos', 'Absorción de gastos de administración con volumen de negocio (E1)'),
    ('margen_rent_gastos', 'Margen de rentabilidad operativa / gastos de estructura (E2)'),
    ('roe', 'ROE: rendimiento anual del patrimonio (R1)'),
    ('roe_ord', 'Rendimiento ordinario del patrimonio (R2)'),
    ('tasa_prest', 'Tasa implícita de préstamos totales (R8)'),
    ('tasa_dep', 'Tasa implícita de depósitos totales (R9)'),
    ('gpers_gadm', 'Gastos en personal / gastos de administración (R17)'),
    ('roa', 'ROA: retorno sobre activos (RG1)'),
    ('margen_fin_activo', 'Margen financiero en términos de activo (RG2_II)'),
    ('roa_inco', 'Cargos por incobrabilidad / activo (RG3)'),
    ('result_serv_activo', 'Resultados por servicios / activo (RG4_II)'),
    ('roa_adm', 'Gastos de administración / activo (RG5)'),
    ('roa_aig', 'ROA antes de impuesto a las ganancias (RG15)'),
    ('liq_amplia', 'Liquidez: títulos con cotización, call, LELIQ y LEFI netos (L1)'),
    ('liq_tit_cot', 'Liquidez con títulos con cotización (L8_II)'),
    ('liq_bcra', 'Liquidez LELIQ, pases y LEFI netos de pases activos BCRA (L9)'),
])
_c('indicadores', 'millones de pesos', False, [
    ('dep_empleado', 'Depósitos por empleado (E4)'),
    ('fin_empleado', 'Financiaciones por empleado (E5)'),
])

# Balance y resultados (mensual). La API publica miles de pesos; acá se
# convierte a millones para coincidir con el PDF.
_c('balance', 'millones de pesos', True, [
    ('bA', 'Activo total'), ('bEf', 'Efectivo y depósitos en bancos'),
    ('bTi', 'Títulos públicos y privados'), ('bPr', 'Préstamos (neto de previsiones)'),
    ('bPr_priv', 'Préstamos al sector privado no financiero y residentes en el exterior'),
    ('bAdel', 'Préstamos: adelantos'), ('bDoc', 'Préstamos: documentos'),
    ('bHip', 'Préstamos: hipotecarios'), ('bPrend', 'Préstamos: prendarios'),
    ('bPers', 'Préstamos: personales'), ('bPrev', 'Previsiones sobre préstamos (negativo)'),
    ('bP', 'Pasivo total'), ('bDe', 'Depósitos totales'),
    ('bDe_priv', 'Depósitos del sector privado no financiero y residentes en el exterior'),
    ('bCC', 'Depósitos privados en cuenta corriente'),
    ('bCA', 'Depósitos privados en caja de ahorros'),
    ('bPF', 'Depósitos privados a plazo fijo e inversiones a plazo'),
    ('bPN', 'Patrimonio neto'),
    ('bRes', 'Resultado integral acumulado del ejercicio a la fecha'),
    ('bIF', 'Ingresos financieros acumulados del ejercicio'),
    ('bEgF', 'Egresos financieros acumulados del ejercicio (negativo)'),
    ('bInc', 'Cargo por incobrabilidad acumulado del ejercicio (negativo)'),
    ('bIS', 'Ingresos por servicios acumulados del ejercicio'),
    ('bES', 'Egresos por servicios acumulados del ejercicio (negativo)'),
    ('bGA', 'Gastos de administración acumulados del ejercicio (negativo)'),
    ('bRM', 'Resultado monetario acumulado del ejercicio'),
    ('bIG', 'Impuesto a las ganancias acumulado del ejercicio'),
])
BAL_MAPA = {
    ('activo', 'ACTIVO'): 'bA', ('activo', 'EFECTIVOYDEPOSITOENBANCOS'): 'bEf',
    ('activo', 'TITULOSPUBLICOSYPRIVADOS'): 'bTi', ('activo', 'PRESTAMOS'): 'bPr',
    ('activo', 'SECTORPRIVADONOFINANCIEROYRESIDENTESENELEXT'): 'bPr_priv',
    ('activo', 'ADELANTOS'): 'bAdel', ('activo', 'DOCASOLAFIRMADESCONTYCOMPRADOS'): 'bDoc',
    ('activo', 'HIPOTECARIOS'): 'bHip', ('activo', 'PRENDARIOS'): 'bPrend',
    ('activo', 'PERSONALES'): 'bPers', ('activo', 'PREVISIONES'): 'bPrev',
    ('pasivo', 'PASIVO'): 'bP', ('pasivo', 'DEPOSITOS'): 'bDe',
    ('pasivo', 'SECTORPRIVADONOFINANCIEROYRESIDENTESENELEXT'): 'bDe_priv',
    ('pasivo', 'CUENTASCORRIENTES'): 'bCC', ('pasivo', 'CAJADEAHORROS'): 'bCA',
    ('pasivo', 'PLAZOFIJOEINVERSIONESAPLAZO'): 'bPF', ('pn', 'PATRIMONIONETO'): 'bPN',
    ('res', 'RDOSINTEGRALESACUMDELPERIODO'): 'bRes', ('res', 'INGRESOSFINANCIEROS'): 'bIF',
    ('res', 'EGRESOSFINANCIEROS'): 'bEgF', ('res', 'CARGOPORINCOBRABILIDAD'): 'bInc',
    ('res', 'INGRESOSPORSERVICIOS'): 'bIS', ('res', 'EGRESOSPORSERVICIOS'): 'bES',
    ('res', 'GASTOSDEADMINISTRACION'): 'bGA', ('res', 'RESULTADOMONETARIO'): 'bRM',
    ('res', 'IMPUESTOALASGANANCIAS'): 'bIG',
}
BAL_SECCION = {'ACTIVO': 'activo', 'PASIVO': 'pasivo', 'PATRIMONIONETO': 'pn',
               'RDOSINTEGRALESACUMDELPERIODO': 'res', 'PARTIDASFUERADEBALANCE': 'fuera',
               'PARTIDASFUERADELBALANCE': 'fuera'}

# Situación de deudores (mensual). Montos en millones de pesos.
_c('cartera', 'millones de pesos', True, [
    ('tf_total', 'Total de financiaciones y garantías otorgadas'),
    ('prev', 'Previsiones por riesgo de incobrabilidad constituidas'),
    ('com_total', 'Cartera comercial'), ('con_total', 'Cartera de consumo o vivienda'),
    ('cac_total', 'Cartera comercial asimilable a consumo'),
])
_c('cartera', '%', False, [
    ('tf_s1', 'Financiaciones en situación 1: normal'),
    ('tf_s2', 'Financiaciones en situación 2: seguimiento especial / riesgo bajo'),
    ('tf_s3', 'Financiaciones en situación 3: con problemas / riesgo medio'),
    ('tf_s4', 'Financiaciones en situación 4: alto riesgo de insolvencia'),
    ('tf_s5', 'Financiaciones en situación 5: irrecuperable'),
    ('tf_irregular', 'Cartera irregular = situaciones 3+4+5 (CALCULADO)'),
    ('tf_garant', 'Financiaciones con garantías preferidas A y B'),
    ('com_part', 'Cartera comercial / financiaciones'),
    ('con_part', 'Cartera de consumo / financiaciones'),
    ('cac_part', 'Cartera comercial asimilable a consumo / financiaciones'),
] + [('%s_s%d' % (p, n), '%s en situación %d' % (d, n))
     for p, d in (('com', 'Cartera comercial'), ('con', 'Cartera de consumo'),
                  ('cac', 'Cartera comercial asimilable a consumo'))
     for n in range(1, 6)] + [
    ('com_garant', 'Cartera comercial con garantías preferidas A y B'),
    ('con_garant', 'Cartera de consumo con garantías preferidas A y B'),
    ('cac_garant', 'Cartera asimilable a consumo con garantías preferidas A y B'),
])

# Información adicional (trimestral). Cantidades.
ADIC_TITULOS = {
    'CANTIDADDECUENTASCORRIENTES': 'cc', 'CANTIDADDECUENTASDEAHORRO': 'cah',
    'CANTIDADDECAJASDEAHORRODEAYUDASOCIAL': 'cah_social',
    'CANTIDADDECUENTASPREVISIONALES': 'cprev',
    'CANTIDADDEOPERACIONESAPLAZOFIJOINDIVIDUOS': 'pf_ind',
    'CANTIDADDEOPERACIONESAPLAZOFIJOEMPRESAS': 'pf_emp',
    'CANTIDADDEOPERACIONESPORPRESTAMOSHIPOTECARIOS': 'op_hip',
    'CANTIDADDEOPERACIONESPORPRESTAMOSPRENDARIOS': 'op_prend',
    'CANTIDADDEOPERACIONESPOROTROSPRESTAMOS': 'op_otros',
    'DOTACIONDEPERSONAL': 'emp', 'CANTIDADDETITULARESPORTARJETASDECREDITO': 'tit',
    'CANTIDADDETARJETASDECREDITOPLASTICOS': 'pla', 'CANTIDADDETARJETASDEDEBITO': 'deb',
}
_c('adicional', 'cantidad', True, [
    ('cc', 'Cuentas corrientes'), ('cah', 'Cuentas (cajas) de ahorro'),
    ('cah_social', 'Cajas de ahorro de ayuda social'), ('cprev', 'Cuentas previsionales'),
    ('pf_ind', 'Operaciones a plazo fijo de individuos'),
    ('pf_emp', 'Operaciones a plazo fijo de empresas'),
    ('op_hip', 'Operaciones de préstamos hipotecarios'),
    ('op_prend', 'Operaciones de préstamos prendarios'),
    ('op_otros', 'Operaciones de otros préstamos'), ('emp', 'Dotación de personal (empleados)'),
    ('tit', 'Titulares de tarjetas de crédito'), ('pla', 'Tarjetas de crédito (plásticos)'),
    ('deb', 'Tarjetas de débito'),
])
_c('remuneraciones', 'cantidad', True, [
    ('remu', 'Cuentas sueldo: cuentas con acreditación de remuneraciones'),
    ('remu_emp', 'Empresas que pagan sueldos por acreditación bancaria'),
])
SUC_COLUMNAS = ['suc_plenas', 'suc_especificas', 'suc_moviles', 'dep_automatizadas',
                'cajeros', 'terminales', 'puestos_promocion', 'agencias']
_c('sucursales', 'cantidad', True, [
    ('sucursales', 'Sucursales totales = plenas + operatoria específica + móviles (CALCULADO)'),
    ('suc_plenas', 'Sucursales plenas'), ('suc_especificas', 'Sucursales de operatoria específica'),
    ('suc_moviles', 'Sucursales móviles'), ('dep_automatizadas', 'Dependencias automatizadas'),
    ('cajeros', 'Cajeros automáticos (ATM)'), ('terminales', 'Terminales de autoservicio'),
    ('puestos_promocion', 'Puestos de promoción'),
    ('agencias', 'Agencias complementarias de servicios financieros'),
    ('suc_exterior', 'Sucursales en el exterior'),
    ('of_representacion', 'Oficinas de representación en el exterior'),
])

SECCIONES = {
    'indicadores': ('indicadores-economicos.php', {'action': 'indicadores'}),
    'balance': ('entidades-financieras-estados-contables.php', {}),
    'cartera': ('entidades-financieras-situacion-deudores.php', {}),
    'adicional': ('entidades-financieras-informacion-estructura.php',
                  {'detalle': '1', 'detalle_sub': ''}),
}
# Secciones lógicas que salen del mismo endpoint
ENDPOINT_DE = {'indicadores': 'indicadores', 'balance': 'balance', 'cartera': 'cartera',
               'adicional': 'adicional', 'remuneraciones': 'adicional',
               'sucursales': 'adicional'}
PAGINA_WEB = {
    'indicadores': BCRA + '/entidades-financieras-indicadores-economicos/?bco={c}&tipo=1',
    'balance': BCRA + '/entidades-financieras-estados-contables?bco={c}&tipo=1',
    'cartera': BCRA + '/entidades-financieras-situacion-deudores?bco={c}&tipo=1',
    'adicional': BCRA + '/entidades-financieras-informacion-estructura?bco={c}&tipo=1&Tit=1',
}


# ---------------------------------------------------------------------------
# Mapeo de filas (común a la API y al PDF)
# ---------------------------------------------------------------------------

# Palabras que el título debe contener para aceptar el código. Antes de 2014
# el BCRA usaba otros códigos (por ejemplo, A11 era "cartera comercial
# irregular" y hoy es "cartera irregular sector privado"): sin esta
# verificación, un PDF viejo asignaría valores al indicador equivocado.
IND_TITULO = {
    'apalancamiento': ['APALANCAMIENTO'], 'perdida_s2a5': ['PERDIDA', '2 A 5'],
    'perdida_s3a5': ['PERDIDA', '3 A 5'], 'irr_tot': ['CARTERA IRREGULAR', 'TOTAL FINANCIACIONES'],
    'irr_priv': ['CARTERA IRREGULAR SECTOR PRIVADO'],
    'part_com': ['PARTICIPACION', 'COMERCIAL'], 'part_cons': ['PARTICIPACION', 'CONSUMO'],
    'prev_irr': ['PREVISIONES', 'IRREGULAR'], 'irr_cons': ['IRREGULAR CONSUMO SECTOR PRIVADO'],
    'irr_com': ['IRREGULAR COMERCIAL SECTOR PRIVADO'], 'exc_prev': ['POSICION DE PREVISIONES'],
    'part_venc': ['CARTERA VENCIDA'], 'efectivo_activo': ['EFECTIVO', 'ACTIVO'],
    'absorc_gastos': ['ABSORCION'], 'margen_rent_gastos': ['MARGEN DE RENTABILIDAD'],
    'dep_empleado': ['DEPOSITOS POR EMPLEADO'], 'fin_empleado': ['FINANCIACIONES POR EMPLEADO'],
    'roe': ['ROE'], 'roe_ord': ['RENDIMIENTO ORDINARIO'], 'tasa_prest': ['TASA', 'PRESTAMOS'],
    'tasa_dep': ['TASA', 'DEPOSITOS'], 'gpers_gadm': ['GASTOS EN PERSONAL'], 'roa': ['ROA'],
    'margen_fin_activo': ['MARGEN FINANCIERO'], 'roa_inco': ['INCOBRABILIDAD', 'ACTIVO'],
    'result_serv_activo': ['SERVICIOS', 'ACTIVO'], 'roa_adm': ['GASTOS DE ADMINISTRACION', 'ACTIVO'],
    'roa_aig': ['ROA', 'ANTES'], 'liq_amplia': ['LIQ'], 'liq_tit_cot': ['LIQUIDEZ', 'COTIZ'],
    'liq_bcra': ['LIQ'],
}


def clave_indicador(titulo):
    m = re.match(r'^\s*([A-Z]{1,2}\d+(?:_II)?)\s*-', titulo)
    if not m:
        return None
    k = IND_CODIGOS.get(m.group(1))
    if k is None:
        return m.group(1).lower()  # código sin clave conocida: no se expone como campo
    t = norm(titulo)
    if not all(p in t for p in IND_TITULO.get(k, [])) or (k == 'roa' and 'ANTES' in t):
        return None
    return k


class MapaCartera:
    """Asigna claves a las filas de 'situación de deudores' (depende del orden)."""

    def __init__(self):
        self.ultimo = 'tf'

    def __call__(self, titulo):
        t = titulo.upper()
        m = re.match(r'^\s*(TF|C\.COM|C\.CON|C\.CAC)\.SIT\.(\d)', t)
        if m:
            pre = {'TF': 'tf', 'C.COM': 'com', 'C.CON': 'con', 'C.CAC': 'cac'}[m.group(1)]
            return '%s_s%s' % (pre, m.group(2))
        m = re.match(r'^\s*C\.(COM|CON|CAC)\.TOTAL GARANTIZADO', t)
        if m:
            return m.group(1).lower() + '_garant'
        k = clave(t)
        if k.startswith('TOTALDEFINANCIACIONES'):
            return 'tf_total'
        if k.startswith('TOTALGARANTIZADO'):
            return 'tf_garant'
        if k.startswith('PREVISIONESPORRIESGO'):
            return 'prev'
        if k.startswith('CARTERACOMERCIALASIMILABLE'):
            self.ultimo = 'cac'
            return 'cac_total'
        if k.startswith('CARTERACOMERCIAL'):
            self.ultimo = 'com'
            return 'com_total'
        if k.startswith('CARTERADECONSUMO'):
            self.ultimo = 'con'
            return 'con_total'
        if k.startswith('TOTALCARTERASOBREFINANCIACIONES'):
            return self.ultimo + '_part'
        return None


class MapaBalance:
    """Asigna claves a las filas del balance según la sección en la que aparecen."""

    def __init__(self):
        self.seccion = None
        self.vistos = set()

    def __call__(self, titulo):
        k = clave(titulo)
        if k in BAL_SECCION:
            self.seccion = BAL_SECCION[k]
        campo = BAL_MAPA.get((self.seccion, k))
        if campo and campo not in self.vistos:
            self.vistos.add(campo)
            return campo
        return None


def _vacio_a_none(v):
    """El BCRA muestra 0 como celda vacía ('---' en el PDF): se informa como null."""
    if v is None or v == '' or v == 0:
        return None
    return v


def _miles_a_millones(v):
    """Miles -> millones con 1 decimal, redondeando como el PDF del BCRA (mitad hacia arriba)."""
    d = (decimal.Decimal(str(v)) / 1000).quantize(decimal.Decimal('0.1'), decimal.ROUND_HALF_UP)
    return float(d)


def _indicador(v):
    """Además del 0, la API usa 99999 como marcador de 'no corresponde' ('---' en el PDF)."""
    if v in (99999, -99999):
        return None
    return _vacio_a_none(v)


def _agregar(res, clave_, periodos, valores, transformar=None):
    serie = {}
    for p, v in zip(periodos, valores):
        if transformar:
            v = transformar(v)
        serie[p] = v
    res['campos'].setdefault(clave_, {}).update(serie)


def _nuevo():
    return {'campos': {}, 'titulos': {}, 'actualizado': None, 'extra': {}}


def _fecha(d):
    f = d.get('fecha_actualizacion') or {}
    return periodo_iso('%s %s' % (f.get('mes', ''), f.get('anio', ''))) if f else None


def normalizar(seccion_api, d):
    """Convierte la respuesta JSON de un endpoint a {'campos': {clave: {periodo: valor}}}."""
    res = _nuevo()
    res['actualizado'] = _fecha(d)
    if seccion_api == 'indicadores':
        cols = d.get('columnas') or {}
        orden = sorted(cols, key=lambda c: int(re.sub(r'\D', '', c) or 0))
        pers = [periodo_iso(cols[c]) for c in orden]
        res['nombre_fuente'] = d.get('en_nombre')
        for filas in (d.get('secciones') or {}).values():
            for f in filas:
                k = clave_indicador(f.get('in_titulo', ''))
                if not k:
                    continue
                vals = [f.get('in_' + c.replace('col', 'c')) for c in orden]
                _agregar(res, k, pers, vals, _indicador)
                res['titulos'][k] = f.get('in_titulo')
    elif seccion_api == 'balance':
        pers = [periodo_iso(x) for x in d.get('fechas') or []]
        mapa = MapaBalance()
        filas = []
        for f in d.get('filas') or []:
            vals = [None if _vacio_a_none(v) is None else _miles_a_millones(v)
                    for v in f.get('valores') or []]
            filas.append({'titulo': ' '.join(f['titulo'].split()), 'nivel': f.get('nivel'),
                          'valores': dict(zip(pers, vals))})
            k = mapa(f['titulo'])
            if k:
                _agregar(res, k, pers, vals)
                res['titulos'][k] = f['titulo']
        res['extra']['filas_balance'] = filas
    elif seccion_api == 'cartera':
        pers = [periodo_iso(x) for x in d.get('columnas') or []]
        res['nombre_fuente'] = d.get('entidad')
        mapa = MapaCartera()
        for f in d.get('filas') or []:
            k = mapa(f.get('titulo', ''))
            if k:
                _agregar(res, k, pers, f.get('valores') or [])
                res['titulos'][k] = f.get('titulo')
        _calcular_irregular(res)
    elif seccion_api == 'adicional':
        ia = d.get('info_adicional') or {}
        pers = [periodo_iso(x) for x in ia.get('cabecera') or []]
        for f in ia.get('filas') or []:
            k = ADIC_TITULOS.get(clave(f.get('titulo', '')))
            if k:
                _agregar(res, k, pers, f.get('valores') or [], _vacio_a_none)
                res['titulos'][k] = f.get('titulo')
        pr = d.get('pago_remuneraciones') or {}
        pers_r = [periodo_iso(x) for x in pr.get('cabecera') or []]
        for f in pr.get('filas') or []:
            k = {'CANTIDADDECUENTAS': 'remu', 'CANTIDADDEEMPRESAS': 'remu_emp'}.get(
                clave(f.get('titulo', '')))
            if k:
                _agregar(res, k, pers_r, f.get('valores') or [], _vacio_a_none)
                res['titulos'][k] = f.get('titulo')
        loc = d.get('localizacion_pais') or []
        per_loc = res['actualizado']
        if loc and per_loc:
            tot = [0] * len(SUC_COLUMNAS)
            prov = {}
            for p in loc:
                vals = (p.get('valores') or [])[:len(SUC_COLUMNAS)]
                prov[p.get('provincia')] = dict(zip(SUC_COLUMNAS, vals))
                for i, v in enumerate(vals):
                    tot[i] += v or 0
            for k, v in zip(SUC_COLUMNAS, tot):
                res['campos'][k] = {per_loc: v}
            res['campos']['sucursales'] = {per_loc: tot[0] + tot[1] + tot[2]}
            res['extra']['por_provincia'] = prov
        ext = d.get('localizacion_exterior') or []
        if per_loc and loc:
            suc = sum((x.get('valores') or [0, 0])[0] or 0 for x in ext)
            ofi = sum(((x.get('valores') or [0, 0]) + [0])[1] or 0 for x in ext)
            res['campos']['suc_exterior'] = {per_loc: suc}
            res['campos']['of_representacion'] = {per_loc: ofi}
            if ext:
                res['extra']['exterior'] = ext
        comp = d.get('composicion_sf')
        if comp:
            pc = [periodo_iso(x) for x in comp.get('cabecera') or []]
            res['extra']['composicion_sistema'] = {
                f['titulo']: dict(zip(pc, f['valores'])) for f in comp.get('filas') or []}
    return res


def _calcular_irregular(res):
    c = res['campos']
    if all(k in c for k in ('tf_s3', 'tf_s4', 'tf_s5')):
        serie = {}
        for p in c['tf_s3']:
            vals = [c[k].get(p) for k in ('tf_s3', 'tf_s4', 'tf_s5')]
            serie[p] = round(sum(v or 0 for v in vals), 2) if any(v is not None for v in vals) else None
        c['tf_irregular'] = serie


def consultar(codigo_api_, secciones):
    """Trae en paralelo las secciones pedidas de una entidad o grupo y las une."""
    endpoints = sorted({ENDPOINT_DE[s] for s in secciones})

    def traer(sec):
        ep, extra = SECCIONES[sec]
        params = dict(extra)
        params.update({'category': codigo_api_, 'lang': 'es'})
        return normalizar(sec, api(ep, **params))

    total = _nuevo()
    total['actualizado_por_seccion'] = {}
    for sec, r in en_paralelo(traer, endpoints):
        if isinstance(r, Exception):
            total['extra'].setdefault('errores', {})[sec] = str(r)
            continue
        total['campos'].update(r['campos'])
        total['titulos'].update(r['titulos'])
        total['extra'].update(r['extra'])
        total['actualizado_por_seccion'][sec] = r['actualizado']
        if r.get('nombre_fuente'):
            total['nombre_fuente'] = r['nombre_fuente']
    fechas = [f for f in total['actualizado_por_seccion'].values() if f]
    total['actualizado'] = max(fechas) if fechas else None
    return total


def ultimo_valor(serie):
    """(periodo, valor) más reciente no nulo de {periodo: valor}."""
    for p in sorted(serie, reverse=True):
        if serie[p] is not None:
            return p, serie[p]
    return None, None


def describir(k):
    sec, desc, unidad, _ = CAMPOS.get(k, (None, k, None, False))
    return {'desc': desc, 'unidad': unidad, 'seccion': sec}


# ---------------------------------------------------------------------------
# PDF mensual "Información de Entidades Financieras"
# ---------------------------------------------------------------------------

def hay_pdftotext():
    return shutil.which('pdftotext') is not None


def exigir_pdftotext():
    if not hay_pdftotext():
        raise ErrorFuente('Falta pdftotext (poppler-utils). Instalar con: '
                          'apt-get install -y poppler-utils  (o brew install poppler). '
                          'Solo hace falta para series históricas y la ficha institucional.')


def pdf_entidades(ym):
    """Descarga (con caché) el PDF del mes 'YYYY-MM' y devuelve la ruta local."""
    url = PDF_ENTIDADES.format(ym=ym.replace('-', ''))
    datos = descargar(url, ttl=max(CACHE_TTL, 86400), timeout=180,
                      validar=lambda b: b[:4] == b'%PDF')
    ruta = _ruta_cache(url)
    if not os.path.exists(ruta):  # caché deshabilitada: guardar temporal
        ruta = os.path.join(tempfile.gettempdir(), 'bcra-%s.pdf' % ym)
        with open(ruta, 'wb') as f:
            f.write(datos)
    return ruta


def pdftotext(ruta, desde, hasta):
    exigir_pdftotext()
    r = subprocess.run(['pdftotext', '-layout', '-f', str(desde), '-l', str(hasta), ruta, '-'],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if r.returncode != 0:
        raise ErrorFuente('pdftotext falló: ' + r.stderr.decode('utf-8', 'replace')[:300])
    return r.stdout.decode('utf-8', 'replace')


def indice_pdf(ruta):
    """Lee el índice del PDF: [(nombre, pagina_impresa)] en orden."""
    texto = pdftotext(ruta, 1, 12)
    items = []
    for linea in texto.split('\n'):
        m = re.match(r'^\s*(.+?)[\s.]*\.\s?\.\s?\.[\s.]*(\d{1,3})\s*$', linea)
        if m:
            nombre = m.group(1).strip().rstrip('.').strip()
            items.append((nombre, int(m.group(2))))
    return items


def paginas_entidad_pdf(ruta, entidad):
    """Devuelve (texto_de_sus_paginas, pagina_inicial) para una entidad o grupo."""
    items = indice_pdf(ruta)
    if not items:
        raise ErrorFuente('No se pudo leer el índice del PDF')
    objetivo = norm(entidad['nombre'])
    idx = None
    for i, (nombre, _) in enumerate(items):
        n = norm(nombre)
        if n == objetivo or n.startswith(objetivo) or objetivo.startswith(n):
            idx = i
            break
    if idx is None and entidad['tipo'] == 'grupo':
        clave_g = {'sistema': 'SISTEMA FINANCIERO', 'publicos': 'BANCOS PUBLICOS',
                   'privados': 'BANCOS PRIVADOS', 'companias': 'COMPANIAS FINANCIERAS',
                   'top10': '10 PRIMEROS BANCOS PRIVADOS'}[entidad['grupo']]
        idx = next((i for i, (n, _) in enumerate(items) if norm(n) == clave_g), None)
    if idx is None:
        raise ErrorFuente('La entidad "%s" no figura en el índice del PDF' % entidad['nombre'])
    inicio = items[idx][1]
    siguientes = [p for _, p in items[idx + 1:] if p > inicio]
    largo = (siguientes[0] - inicio) if siguientes else 4
    # La numeración impresa y la del archivo difieren en una cantidad que
    # cambia según el mes (de 0 a 3 en los PDF revisados), pero es constante
    # dentro de cada documento.
    if entidad['tipo'] == 'entidad':
        cod = '%s - ' % codigo_api(entidad['codigo'])
        desde = max(1, inicio - 3)
        ventana = pdftotext(ruta, desde, inicio + 8).split('\f')
        for i, pag in enumerate(ventana):
            if pag.lstrip().startswith(cod):
                return pdftotext(ruta, desde + i, desde + i + largo - 1), desde + i
        raise ErrorFuente('No se ubicaron las páginas de "%s" en el PDF' % entidad['nombre'])
    desfase = _desfase_pdf(ruta, items)
    if desfase is None:
        raise ErrorFuente('No se pudo ubicar la sección "%s" en el PDF' % entidad['nombre'])
    return pdftotext(ruta, inicio + desfase, inicio + desfase + largo - 1), inicio + desfase


def _desfase_pdf(ruta, items):
    """Diferencia entre la página impresa en el índice y la página del archivo.

    Se mide con las primeras entidades del índice, cuya primera línea es
    'CODIGO - NOMBRE'.
    """
    candidatos = [(n, p) for n, p in items if re.match(r'(?i)^(BANCO|BACS)\b', n)][:3]
    for nombre, pag in candidatos:
        desde = max(1, pag - 3)
        for i, texto in enumerate(pdftotext(ruta, desde, pag + 8).split('\f')):
            m = re.match(r'\s*\d{5} - (.+)', texto)
            if m and (norm(m.group(1)).startswith(norm(nombre)) or
                      norm(nombre).startswith(norm(m.group(1)))):
                return desde + i - pag
    return None


PER_RE = re.compile(r'\b(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Set|Oct|Nov|Dic)-(\d{4})\b')
# Los PDF más viejos imprimen los millones sin separador: '1477.466,3'
NUM_RE = re.compile(r'^-?\d+(?:\.\d{3})*(?:,\d+)?%?$|^---$')


def filas_pdf(texto):
    """Extrae filas 'etiqueta  v1  v2 ...' asignando cada valor a la cabecera vigente.

    Devuelve [(etiqueta, {periodo: valor}, [extras])]. Los extras son columnas
    sin período (en Indicadores: grupo institucional, 10 primeros, sistema).
    """
    filas = []
    cab = None
    for linea in texto.split('\n'):
        pers = PER_RE.findall(linea)
        if len(pers) >= 3:
            cab = [periodo_iso('%s-%s' % p) for p in pers]
            continue
        tokens = linea.split()
        if not tokens:
            continue
        # Los valores son la última racha de números de la línea. Se buscan
        # token por token porque a veces dos columnas quedan separadas por un
        # solo espacio; se descarta texto suelto del margen al final.
        fin = len(tokens)
        while fin > 0 and not NUM_RE.match(tokens[fin - 1]):
            fin -= 1
        ini = fin
        while ini > 0 and NUM_RE.match(tokens[ini - 1]):
            ini -= 1
        etiqueta = ' '.join(tokens[:ini]) if ini else ' '.join(tokens)
        if not re.search(r'[A-Za-z]', etiqueta):
            continue
        if cab is None or ini == fin:
            filas.append((re.split(r'\s{2,}', linea.strip())[0], None, []))  # marcador
            continue
        nums = [num_ar(v) for v in tokens[ini:fin]]
        if len(nums) < len(cab):
            continue  # fila incompleta: no se adivina a qué período corresponde cada valor
        filas.append((etiqueta, dict(zip(cab, nums[:len(cab)])), nums[len(cab):]))
    return filas


def normalizar_pdf(texto):
    """Mapea las filas del PDF de una entidad a las mismas claves que la API."""
    res = _nuevo()
    mapa_bal, mapa_car = MapaBalance(), MapaCartera()
    bloque = None
    ref = {}
    for etiqueta, serie, extras in filas_pdf(texto):
        k_et = clave(etiqueta)
        if k_et.startswith('EVOLUCIONDEESTADOSCONTABLES'):
            bloque = 'balance'
        elif k_et == 'INDICADORES':
            bloque = 'indicadores'
        elif k_et.startswith('INFORMACIONADICIONAL'):
            bloque = 'adicional'
        elif k_et.startswith('PAGODEREMUNERACIONES'):
            bloque = 'remuneraciones'
        elif k_et.startswith('ESTADODESITUACIONDEDEUDORES') or k_et.startswith('COMPOSICIONDECARTERA'):
            bloque = 'cartera'
        if bloque == 'balance':
            k = mapa_bal(etiqueta)
        elif bloque == 'indicadores':
            k = clave_indicador(etiqueta)
        elif bloque == 'adicional':
            k = ADIC_TITULOS.get(k_et)
        elif bloque == 'remuneraciones':
            k = {'CANTIDADDECUENTAS': 'remu', 'CANTIDADDEEMPRESAS': 'remu_emp'}.get(k_et)
        elif bloque == 'cartera':
            k = mapa_car(etiqueta)
        else:
            k = None
        if not k or serie is None:
            continue
        res['campos'].setdefault(k, {}).update(serie)
        res['titulos'][k] = etiqueta
        if bloque == 'indicadores' and len(extras) >= 3:
            ref[k] = {'grupo_institucional': extras[0], 'diez_primeros': extras[1],
                      'sistema': extras[2]}
    _calcular_irregular(res)
    if ref:
        res['extra']['referencias'] = ref
    return res


def ficha_pdf(texto):
    """Datos institucionales de la primera página: directivos, accionistas, auditor."""
    pag = texto.split('\f')[0]
    lineas = [l.rstrip() for l in pag.split('\n')]
    ficha = {'directivos': [], 'accionistas': []}
    modo = None
    for l in lineas:
        s = l.strip()
        if not s:
            continue
        if s.startswith('CUIT:'):
            ficha['cuit'] = s.split(':', 1)[1].strip()
        elif s.startswith('Casa Matriz'):
            ficha['casa_matriz'] = s.split('-', 1)[1].strip() if '-' in s else s
        elif s.startswith('Web:'):
            ficha['contacto'] = re.split(r'\s{2,}', s)[0]
        elif s.startswith('Asociado a:'):
            ficha['asociado_a'] = s.split(':', 1)[1].strip()
        n = norm(s)
        if n.startswith('NOMINA DE DIRECTIVOS'):
            modo = 'dir'
            continue
        if n.startswith('NOMINA DE ACCIONISTAS'):
            modo = 'acc'
            continue
        if n.startswith('AUDITORES EXTERNOS'):
            modo = 'aud'
            continue
        if n.startswith('LOCALIZACION'):
            modo = None
            continue
        partes = [p.strip() for p in re.split(r'\s{2,}', s) if p.strip()]
        while len(partes) > 1 and re.fullmatch(r'\d+', partes[-1]):
            partes.pop()  # números sueltos del gráfico lateral del PDF
        if modo == 'dir' and len(partes) >= 2 and re.match(r'^[A-ZÁÉÍÓÚÑ .]+$', partes[0]) \
                and re.search(r'[A-ZÁÉÍÓÚÑ]{2,}', partes[1]) and not re.match(r'^\d', partes[1]):
            ficha['directivos'].append({'cargo': partes[0], 'nombre': partes[1]})
        elif modo == 'acc' and len(partes) >= 3 and partes[1].endswith('%'):
            ficha['accionistas'].append({'nombre': partes[0], 'capital': partes[1],
                                         'votos': partes[2]})
        elif modo == 'aud' and partes and partes[0].startswith(('AUDITOR', 'SOCIO')):
            ficha.setdefault('auditores', []).append(' | '.join(partes))
    for linea in lineas[:10]:
        if re.search(r'(Bancos|Compañías|Companias) ', linea) and 'Asociado' not in linea:
            ficha['grupo_institucional'] = linea.strip()
            break
    return ficha
