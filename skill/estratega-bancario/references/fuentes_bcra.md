# Fuentes oficiales y trampas conocidas

> **Copia de referencia del skill [bcra-oraculo](https://github.com/AGVD-CODE/BCRA-Oracle)** (mismo autor, licencia MIT). Los comandos que menciona (`consultar_entidad.py`, `consultar_historico.py`, etc.) son de ese skill; en estratega-bancario el acceso a estas fuentes lo hace `scripts/bcra_comun.py` a través de `panel_bcra.py`. Las claves de campos son las mismas.


Los scripts ya resuelven todo lo que sigue. Leer este documento solo si un script falla o si una fuente cambió. Las URLs y formatos se verificaron en octubre de 2026.

## Índice
1. BCRA: API de Información de Entidades Financieras (fuente principal)
2. BCRA: PDF mensual de Información de Entidades Financieras (historia y ficha)
3. BCRA: Informe Mensual de Pagos Minoristas (XLSX)
4. INDEC: IPC Nacional (CSV)
5. Acceso de red
6. Valores de control para verificar que el parseo sigue funcionando
7. Si una fuente cambia

---

## 1. BCRA: API de Información de Entidades Financieras

Es la API JSON que usan las páginas de "Información de Entidades Financieras" de www.bcra.gob.ar. Responde en ~1 segundo con pocos KB por entidad y sección. Es lo que usan `consultar_entidad.py` y `consultar_ranking.py`.

| Sección | Endpoint (`https://www.bcra.gob.ar/api/endpoints/...`) | Parámetros |
|---|---|---|
| Nómina de entidades | `nomina-entidades.php` | `action=nomina_AAA00&lang=es` |
| Indicadores | `indicadores-economicos.php` | `action=indicadores&category=00007&lang=es` |
| Estados contables | `entidades-financieras-estados-contables.php` | `category=00007&lang=es` |
| Situación de deudores | `entidades-financieras-situacion-deudores.php` | `category=00007&lang=es` |
| Información de estructura (adicional, cuentas sueldo, sucursales) | `entidades-financieras-informacion-estructura.php` | `category=00007&detalle=1&detalle_sub=&lang=es` |

- `category` es el código BCRA de 5 dígitos (Galicia = `00007`) o un grupo: `AAA00` sistema financiero, `AAA10` públicas, `AAA20` privadas, `AAA30` compañías financieras, `AAA50` 10 primeros bancos privados.
- Cada respuesta trae `fecha_actualizacion` (mes de la última información) y 5 columnas de períodos.

**Trampas:**
- **Unidades distintas por sección.** Estados contables en **miles** de pesos (el script convierte a millones). Situación de deudores en **millones**. Indicadores en %.
- **El 0 significa "sin dato".** La web del BCRA muestra el 0 como celda vacía, y el PDF muestra "---". En indicadores, además, aparece **99999** como marcador de "no corresponde". Los scripts convierten ambos en `null`. Sin este filtro, un ranking de mora de consumo pondría primero a una entidad con 99999 %.
- **Nombres truncados.** La nómina corta los nombres a 40 caracteres y algunos endpoints a 35.
- **Información adicional trimestral con ceros.** Un trimestre recién publicado puede venir incompleto: algunas filas en 0 (convertidas a `null`).

**Páginas para citar** (reemplazar `00007` por el código de la entidad):
- Indicadores: `https://www.bcra.gob.ar/entidades-financieras-indicadores-economicos/?bco=00007&tipo=1`
- Estados contables: `https://www.bcra.gob.ar/entidades-financieras-estados-contables?bco=00007&tipo=1`
- Situación de deudores: `https://www.bcra.gob.ar/entidades-financieras-situacion-deudores?bco=00007&tipo=1`
- Información de estructura: `https://www.bcra.gob.ar/entidades-financieras-informacion-estructura?bco=00007&tipo=1&Tit=1`
- Total del sistema: `https://www.bcra.gob.ar/total-del-sistema-financiero/`

La página vieja `https://www.bcra.gob.ar/PublicacionesEstadisticas/Entidades_financieras.asp` devuelve 404. No citarla.

---

## 2. BCRA: PDF mensual de Información de Entidades Financieras

`https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/Entidades/YYYYMMe.pdf` (julio 2026: `202607e.pdf`).

Lo usan `consultar_historico.py` (series de más de 5 períodos) y `consultar_entidad.py --seccion ficha` (directivos, accionistas, auditor, contacto, que la API no publica).

- **Tamaño variable:** entre 3,5 y 17 MB según el mes, con la misma estructura (387 páginas).
- **Estructura:** índice en las páginas 5-6 y luego 4 páginas por entidad: (1) ficha y localización, (2) estados contables en millones, (3) indicadores con columnas de referencia (grupo institucional, 10 primeros, sistema), (4) información adicional, cuentas sueldo y situación de deudores. La primera línea de cada entidad es `CODIGO - NOMBRE` (por ejemplo `00007 - BANCO DE GALICIA...`).
- **Velocidad:** el script lee el índice y convierte solo las 4 páginas de la entidad con `pdftotext -layout -f N -l M` (~0,1 s), no el documento entero (~5 s).
- **Cobertura:** cada PDF trae los 3 últimos meses más los 2 últimos diciembres. Para 12 meses alcanzan 4 PDF (uno cada 3 meses).
- **Historia disponible (probado en octubre de 2026):** completa desde 2014. En 2011-2013 se leen balance, información adicional y ROE, pero no los indicadores de mora: el BCRA usaba otros códigos (por ejemplo, A11 era "cartera comercial irregular"). El script verifica el título de cada indicador y no informa los que no coinciden, para no atribuir un valor al indicador equivocado. En 2010 y antes el índice del PDF tiene otro formato y no se lee.
- **Revisiones:** el valor de un mes puede cambiar entre ediciones del PDF. Si varios PDF descargados traen el mismo mes, el script usa el más reciente.
- **Mes no publicado:** el servidor responde 404 con una página HTML. El script valida que el archivo empiece con `%PDF`.
- **Numeración de páginas:** la página impresa en el índice y la página del archivo difieren entre 0 y 3 según el mes. El script busca la página que empieza con el código de la entidad. Para los grupos mide esa diferencia con una entidad del mismo PDF.

**Trampas:**
- **Columnas pegadas.** A veces dos números quedan separados por un solo espacio. El parser toma los valores token por token desde el final de la línea. Si una fila tiene menos valores que períodos, la descarta en lugar de adivinar.
- **Millones sin separador.** Los PDF más viejos imprimen `1477.466,3` en lugar de `1.477.466,3`. El parser acepta los dos formatos.
- **Texto lateral.** El nombre de la entidad aparece en vertical en el margen y se mezcla con algunas líneas. Se ignora.
- **Trimestre reciente incompleto.** En el PDF de un mes, el último trimestre de "Información adicional" puede tener casi todo en "---". El PDF del mes siguiente lo completa.
- **Requiere `pdftotext`** (paquete poppler-utils). No es un paquete de pip.

---

## 3. BCRA: Informe Mensual de Pagos Minoristas (XLSX)

`https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/Informes/series-informe-mensual-pagos-minoristas-YYYY-MM.xlsx` (~170 KB). Un solo archivo trae la serie completa desde 2017.

- **El último archivo no tiene fecha fija.** El script prueba en paralelo los últimos 6 meses y se queda con el más reciente que sea un XLSX válido (empieza con `PK`). Las peticiones HEAD no sirven: el servidor responde 200 aunque el archivo no exista.
- **Estructura:** 9 hojas. Cada una tiene 1 a 3 filas de encabezado (con celdas combinadas), una fila `Fecha` y pares de columnas cantidad / monto. "TC Modalidad de pago" tiene la fila cantidad/monto debajo de `Fecha`. "Tarjeta de credito por canal" tiene el monto en una columna con otro título ("POS+QR Monto"). "Cuentas de pago y fondos invert" tiene dos tablas lado a lado con su propia columna `Fecha`. El script maneja los tres casos.
- **Rezago distinto por hoja:** por ejemplo, transferencias a agosto y tarjetas a julio en la misma edición.
- **Lectura sin dependencias:** el script lee el XLSX con `zipfile` y `xml` de la biblioteca estándar. Se verificó celda por celda contra openpyxl (11.258 celdas, 0 diferencias).

Página para citar: `https://www.bcra.gob.ar/informe-de-pagos-minoristas/`

---

## 4. INDEC: IPC Nacional (CSV)

`https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv` (~1,2 MB, separador `;`, decimales con coma, codificación Latin-1).

- **URL fija y siempre actualizada.** No hay que adivinar el nombre del archivo.
- **Columnas:** `Codigo; Descripcion; Clasificador; Periodo (YYYYMM); Indice_IPC; v_m_IPC; v_i_a_IPC; Region`. Incluye nivel general, 12 divisiones, núcleo, regulados, estacional, bienes y servicios, para 7 regiones.
- **Acumuladas:** se calculan con el índice (índice final / índice del mes anterior al inicio − 1), que reproduce el dato oficial. Encadenar variaciones mensuales redondeadas da diferencias de una décima (2024: 117,7 % encadenado contra 117,8 % oficial).

**Trampa del archivo XLS (motivo del cambio a CSV):** el XLS `sh_ipc_MM_YY.xls` se nombra por mes de publicación y un mes futuro devuelve una página de ~36 KB. En octubre de 2026, `sh_ipc_10_26.xls` seguía siendo esa página aunque el CSV ya traía el dato de septiembre. La regla "probar desde el mes actual hacia atrás" daba un mes de atraso.

Archivo con más apertura (por región y producto): `serie_ipc_aperturas.csv`, en la misma carpeta.

Página para citar: `https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-5-31`

---

## 5. Acceso de red

Los scripts necesitan salida a `www.bcra.gob.ar` e `www.indec.gob.ar`. Muchos entornos de ejecución de código solo permiten dominios de una lista. Si un script responde `sin_acceso_red: true`:

1. Pedir al usuario que agregue esos dominios a la lista de dominios permitidos (o que habilite el acceso de red completo) en la configuración de ejecución de código de su entorno, y que vuelva a preguntar.
2. Como alternativa, el usuario puede descargar el archivo (PDF, XLSX o CSV) y subirlo. `consultar_pagos.py` acepta `--archivo`.
3. Nunca responder de memoria mientras tanto.

---

## 6. Valores de control

Para confirmar que el parseo sigue funcionando. Son publicaciones cerradas: no cambian.

**PDF de abril de 2026 (`202604e.pdf`), Banco Galicia (código 7), abril de 2026:**
`irr_tot` = 8,09 · `irr_cons` = 16,17 · `irr_com` = 3,32 · `roa` = 0,04 · `apalancamiento` = 4,3 · `tasa_prest` = 32,4 · `bA` = 36.704.435,9 · `bCA` = 12.339.200,7

```bash
python3 scripts/consultar_historico.py Galicia --campo irr_tot bA --desde 2026-04 --hasta 2026-04
```

**INDEC, nivel general nacional:** noviembre 2025 mensual = 2,5 · mayo 2026 mensual = 2,1 · acumulada 2024 = 117,8 · acumulada 2025 = 31,5.

```bash
python3 scripts/consultar_ipc.py --acumulado 2024
```

**API frente a PDF:** en julio de 2026 se compararon los 34.255 valores que comparten la API y el PDF para las 73 entidades. Coincidieron todos salvo 4: montos menores a 0,05 millones que el PDF muestra como "---" y la API como un valor mínimo.

`python3 tools/verificar.py`, en la raíz del repositorio, corre estas comprobaciones.

---

## 7. Si una fuente cambia

El BCRA y el INDEC cambian formatos y URLs sin aviso (el sitio del BCRA cambió de diseño y de URLs: la página que citaba la versión anterior de este skill hoy da 404). Si un script falla:

1. Leer el error: dice qué URL falló y por qué.
2. Abrir la página oficial para citar de la fuente y buscar el nuevo enlace o el nuevo formato.
3. Si el cambio es de URL, ajustar la constante al principio del script (`API`, `PDF_ENTIDADES` en `bcra_comun.py`; `URL` en `consultar_pagos.py` y `consultar_ipc.py`).
4. Si el cambio es de formato, inspeccionar el archivo descargado y adaptar el parseo. Verificar con los valores de control antes de responder.
5. Si no se puede resolver, decir al usuario que la fuente cambió y que no es posible obtener el dato ahora. No responder con un valor no verificado.
