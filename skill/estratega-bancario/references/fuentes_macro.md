# Fuentes macro: catálogo, endpoints y trampas

`macro_ar.py` ya resuelve todo esto. Leé este documento si necesitás una serie que no está en el catálogo o si una fuente falla. Las URLs y los ids se verificaron en octubre de 2026.

## Catálogo (`python3 scripts/macro_ar.py --catalogo`)

| Alias | Fuente e id | Unidad | Mensualización |
|---|---|---|---|
| `ipc`, `ipc_nucleo` | INDEC, CSV del IPC Nacional | índice dic-2016 = 100 | mensual |
| `expectativa_inflacion` | BCRA 29 (REM, próximos 12 meses) | % | mensual |
| `cer`, `uva` | BCRA 30 y 31 | índice y pesos | fin de mes |
| `tc_mayorista`, `tc_minorista` | BCRA 5 y 4 | $/USD | promedio |
| `reservas` | BCRA 1 | millones de USD | fin de mes |
| `badlar`, `tasa_pf30`, `tasa_personales`, `tasa_adelantos`, `tasa_caja_ahorro` | BCRA 7, 12, 14, 13 y 1203 | % TNA | promedio |
| `base_monetaria` | BCRA 15 | millones de pesos | fin de mes |
| `prest_priv_total`, `prest_priv_pesos`, `prest_priv_usd` | BCRA 26, 117 y 125 | millones de pesos / USD | fin de mes |
| `prest_adelantos` … `prest_tarjetas` | BCRA 110 a 115 (en pesos) | millones de pesos | fin de mes |
| `dep_priv_pesos`, `dep_priv_cc`, `dep_priv_ca`, `dep_priv_pf`, `dep_priv_uva`, `dep_priv_usd` | BCRA 100, 94, 95, 96, 97 y 108 | millones de pesos / USD | fin de mes |
| `emae`, `emae_desest` | datos.gob.ar 143.3_NO_PR_2004_A_21 y _A_31 | índice 2004 = 100 | mensual |
| `pbi_real` | datos.gob.ar 9.2_PP2_2004_T_16 | millones de pesos de 2004 | trimestral (último mes del trimestre) |
| `salarios`, `salarios_registrados` | datos.gob.ar 149.1_TL_INDIIOS_OCTU_0_21 y 149.1_TL_REGIADO_OCTU_0_16 | índice oct-2016 = 100 | mensual |
| `ripte` | datos.gob.ar 158.1_REPTE_0_0_5 | pesos | mensual |
| `desocupacion` | datos.gob.ar 42.3_EPH_PUNTUATAL_0_M_30 | % | trimestral (último mes del trimestre) |
| `super_tarjeta_credito` | datos.gob.ar 455.1_TARJETAS_CITO_0_M_16_85 | miles de pesos corrientes | mensual |

Derivadas (CALCULADO): `inflacion_m`, `inflacion_ia`, `salario_real`, `tasa_real_pf`, `tasa_real_personales` (tasa mensual efectiva contra inflación del mes, anualizada), `tc_real` (tipo de cambio deflactado por IPC local, sin inflación externa: es una aproximación), `emae_ia`, `brecha_minorista`.

## Agregar series

```bash
python3 scripts/macro_ar.py --buscar "prendarios automotores"    # busca en BCRA y en datos.gob.ar
python3 scripts/macro_ar.py --series ipc --bcra-id 1126 --datos-id 89.1_TS_INTEIOS_0_M_32 --salida m.csv
python3 scripts/macro_ar.py --series ipc --bcra-id 1203 --promediar --salida m.csv  # tasas: promedio mensual
```

Las columnas nuevas se llaman `bcra_<id>` y `datos_<id>`. Antes de usar una serie nueva, confirmá su unidad en los metadatos (`--buscar` la muestra): algunas series de datos.gob.ar tienen unidades ambiguas, y es mejor no usarlas que interpretarlas mal.

## Endpoints

- **BCRA, API de Estadísticas v4:** `https://api.bcra.gob.ar/estadisticas/v4.0/monetarias` lista unas 1.600 variables (`idVariable`, `descripcion`, `categoria`, `moneda`, `unidadExpresion`, `periodicidad`, primera y última fecha). Datos: `.../monetarias/{id}?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&limit=3000&offset=N`. Como máximo 3.000 filas por página: hay que paginar con `offset`.
- **datos.gob.ar, Series de Tiempo:** `https://apis.datos.gob.ar/series/api/series/?ids=ID&start_date=YYYY-MM&limit=5000&format=json`. Búsqueda: `https://apis.datos.gob.ar/series/api/search/?q=texto`.
- **INDEC, IPC:** `https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv` (separador `;`, coma decimal, Latin-1; región "Nacional"). Es la fuente más actualizada del IPC; datos.gob.ar suele tener un mes menos.

## Trampas conocidas

- **Frecuencias mezcladas en datos.gob.ar:** si se piden juntas una serie mensual y una trimestral, la API lleva todo a trimestral. El script pide una serie por consulta.
- **Trimestrales fechadas al inicio del trimestre** (2026-04-01 = segundo trimestre): el script las corre al último mes (2026-06).
- **Desocupación como fracción** (0,079): el script la pasa a %.
- **CER y UVA se publican por adelantado:** el script corta en el mes en curso.
- **IPC nacional desde dic-2016:** antes, el script empalma con el CER y lo avisa. Para 2014-2016 la inflación es una aproximación.
- **Moneda (campo `moneda`):** ML = pesos, ME = dólares, MEyML = total en pesos. Mirar también `unidadExpresion`: algunas series en dólares vienen en millones de USD y otras, valuadas en pesos.
- **Miles o millones:** las series "por tipo de titular" vienen en miles de pesos; las principales, en millones.
- **"Préstamos por tipo de titular" por provincia** son préstamos a los **gobiernos** provinciales (sector público), no crédito privado por provincia. No usarlas como mapa de crédito regional.
- **Series diarias:** stocks a fin de mes; tasas y tipo de cambio en promedio mensual. Para el tipo de cambio de cierre (por ejemplo, para valuar un stock en dólares) usar `--bcra-id 5` sin `--promediar`.
- **Medios de pago:** el Informe de Pagos Minoristas (transferencias, QR, tarjetas, ECHEQ, cuentas de pago) no está incluido en este skill: lo consulta el skill complementario `bcra-oraculo` (`scripts/consultar_pagos.py --buscar "..." --meses N`), si está instalado, o se baja del sitio del BCRA (URL en `references/fuentes_bcra.md`, sección 3).
