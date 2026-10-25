# Diccionario de datos

> **Copia de referencia del skill [bcra-oraculo](https://github.com/AGVD-CODE/BCRA-Oracle)** (mismo autor, licencia MIT). Los comandos que menciona (`consultar_entidad.py`, `consultar_historico.py`, etc.) son de ese skill; en estratega-bancario el acceso a estas fuentes lo hace `scripts/bcra_comun.py` a través de `panel_bcra.py`. Las claves de campos son las mismas.


Qué es cada campo que devuelven los scripts, en qué sección vive, su unidad y su frecuencia. Las claves son las mismas en todos los scripts (`consultar_entidad.py`, `consultar_ranking.py`, `consultar_historico.py`). La lista también sale de `python3 scripts/consultar_entidad.py --campos`.

## Cómo leer los datos

- **Dato directo:** viene tal cual de la publicación oficial.
- **Dato calculado:** el script o la respuesta lo derivan de datos directos. Los campos calculados dicen "(CALCULADO)" en su descripción. Al responder, aclarar la fórmula.
- **`null`:** la fuente no publica el dato (celda vacía o "---"). Nunca es cero. El BCRA muestra el 0 como celda vacía y usa 99999 como marcador de "no corresponde": los scripts convierten ambos en `null`.
- **Período "YYYY-MM":** mes al que corresponde el dato (no el mes en que se publicó).

## Frecuencia y rezago

| Sección | Frecuencia | Períodos que trae la API | Rezago habitual |
|---|---|---|---|
| `indicadores`, `balance`, `cartera` | mensual | 2 últimos diciembres + 3 últimos meses | unos 3 meses |
| `remuneraciones` (cuentas sueldo) | mensual | 2 últimos diciembres + 3 últimos meses | unos 3 meses |
| `sucursales` | foto al mes de actualización | solo el último | unos 3 meses |
| `adicional` (tarjetas, cuentas, empleados) | trimestral | 3 últimos diciembres + 2 últimos trimestres | unos 4 meses |

Para más historia que la que trae la API, `consultar_historico.py` lee los PDF mensuales (cada uno trae 3 meses consecutivos más 2 diciembres).

---

## Indicadores (BCRA · mensual)

Los publica el BCRA ya calculados. El código oficial del indicador va entre paréntesis. El PDF agrega, para cada indicador, el valor del grupo institucional, de los 10 primeros bancos privados y del sistema (`consultar_historico.py` los devuelve en `referencias` cuando están).

| Campo | Qué es | Unidad |
|---|---|---|
| `apalancamiento` | Apalancamiento: activo / patrimonio neto (C1) | veces |
| `perdida_s2a5` | Pérdida potencial de cartera en situación 2 a 5 (C2) | % |
| `perdida_s3a5` | Pérdida potencial de cartera en situación 3 a 5 (C3) | % |
| `irr_tot` | Mora total: cartera irregular / financiaciones totales (A9) | % |
| `irr_priv` | Cartera irregular del sector privado (A11) | % |
| `part_com` | Participación de la cartera comercial en el sector privado (A12) | % |
| `part_cons` | Participación de la cartera de consumo en el sector privado (A13) | % |
| `prev_irr` | Cobertura: previsiones / cartera irregular total (A14) | % |
| `irr_cons` | Mora de consumo: cartera irregular consumo sector privado (A16) | % |
| `irr_com` | Mora comercial: cartera irregular comercial sector privado (A17) | % |
| `exc_prev` | Posición de previsiones mínimas sector privado no financiero (A21) | % |
| `part_venc` | Importancia de la cartera vencida del sector privado (AG3) | % |
| `efectivo_activo` | Efectivo y depósitos en bancos / activo (AG29) | % |
| `absorc_gastos` | Absorción de gastos de administración con volumen de negocio (E1) | % |
| `margen_rent_gastos` | Margen de rentabilidad operativa / gastos de estructura (E2) | % |
| `roe` | ROE: rendimiento anual del patrimonio (R1) | % |
| `roe_ord` | Rendimiento ordinario del patrimonio (R2) | % |
| `tasa_prest` | Tasa implícita de préstamos totales (R8) | % |
| `tasa_dep` | Tasa implícita de depósitos totales (R9) | % |
| `gpers_gadm` | Gastos en personal / gastos de administración (R17) | % |
| `roa` | ROA: retorno sobre activos (RG1) | % |
| `margen_fin_activo` | Margen financiero en términos de activo (RG2_II) | % |
| `roa_inco` | Cargos por incobrabilidad / activo (RG3) | % |
| `result_serv_activo` | Resultados por servicios / activo (RG4_II) | % |
| `roa_adm` | Gastos de administración / activo (RG5) | % |
| `roa_aig` | ROA antes de impuesto a las ganancias (RG15) | % |
| `liq_amplia` | Liquidez: títulos con cotización, call, LELIQ y LEFI netos (L1) | % |
| `liq_tit_cot` | Liquidez con títulos con cotización (L8_II) | % |
| `liq_bcra` | Liquidez LELIQ, pases y LEFI netos de pases activos BCRA (L9) | % |
| `dep_empleado` | Depósitos por empleado (E4) | millones de pesos |
| `fin_empleado` | Financiaciones por empleado (E5) | millones de pesos |

**Mora a secas = `irr_tot`.** La cartera irregular son las financiaciones en situación 3, 4 y 5 (más de 90 días de atraso).

---

## Balance y resultados (BCRA · mensual)

Millones de pesos corrientes (la API publica miles de pesos y el script divide por 1.000; el PDF ya viene en millones). Los resultados (`bRes`, `bIF`, `bGA`, etc.) son **acumulados desde el inicio del ejercicio**, no del mes. Para el balance completo con los títulos originales: `consultar_entidad.py X --seccion balance --filas`.

| Campo | Qué es | Unidad |
|---|---|---|
| `bA` | Activo total | millones de pesos |
| `bEf` | Efectivo y depósitos en bancos | millones de pesos |
| `bTi` | Títulos públicos y privados | millones de pesos |
| `bPr` | Préstamos (neto de previsiones) | millones de pesos |
| `bPr_priv` | Préstamos al sector privado no financiero y residentes en el exterior | millones de pesos |
| `bAdel` | Préstamos: adelantos | millones de pesos |
| `bDoc` | Préstamos: documentos | millones de pesos |
| `bHip` | Préstamos: hipotecarios | millones de pesos |
| `bPrend` | Préstamos: prendarios | millones de pesos |
| `bPers` | Préstamos: personales | millones de pesos |
| `bPrev` | Previsiones sobre préstamos (negativo) | millones de pesos |
| `bP` | Pasivo total | millones de pesos |
| `bDe` | Depósitos totales | millones de pesos |
| `bDe_priv` | Depósitos del sector privado no financiero y residentes en el exterior | millones de pesos |
| `bCC` | Depósitos privados en cuenta corriente | millones de pesos |
| `bCA` | Depósitos privados en caja de ahorros | millones de pesos |
| `bPF` | Depósitos privados a plazo fijo e inversiones a plazo | millones de pesos |
| `bPN` | Patrimonio neto | millones de pesos |
| `bRes` | Resultado integral acumulado del ejercicio a la fecha | millones de pesos |
| `bIF` | Ingresos financieros acumulados del ejercicio | millones de pesos |
| `bEgF` | Egresos financieros acumulados del ejercicio (negativo) | millones de pesos |
| `bInc` | Cargo por incobrabilidad acumulado del ejercicio (negativo) | millones de pesos |
| `bIS` | Ingresos por servicios acumulados del ejercicio | millones de pesos |
| `bES` | Egresos por servicios acumulados del ejercicio (negativo) | millones de pesos |
| `bGA` | Gastos de administración acumulados del ejercicio (negativo) | millones de pesos |
| `bRM` | Resultado monetario acumulado del ejercicio | millones de pesos |
| `bIG` | Impuesto a las ganancias acumulado del ejercicio | millones de pesos |

---

## Situación de deudores (BCRA · mensual)

Montos en millones de pesos. Porcentajes sobre el total de cada cartera.

| Campo | Qué es | Unidad |
|---|---|---|
| `tf_total` | Total de financiaciones y garantías otorgadas | millones de pesos |
| `prev` | Previsiones por riesgo de incobrabilidad constituidas | millones de pesos |
| `com_total` | Cartera comercial | millones de pesos |
| `con_total` | Cartera de consumo o vivienda | millones de pesos |
| `cac_total` | Cartera comercial asimilable a consumo | millones de pesos |
| `tf_s1` | Financiaciones en situación 1: normal | % |
| `tf_s2` | Financiaciones en situación 2: seguimiento especial / riesgo bajo | % |
| `tf_s3` | Financiaciones en situación 3: con problemas / riesgo medio | % |
| `tf_s4` | Financiaciones en situación 4: alto riesgo de insolvencia | % |
| `tf_s5` | Financiaciones en situación 5: irrecuperable | % |
| `tf_irregular` | Cartera irregular = situaciones 3+4+5 (CALCULADO) | % |
| `tf_garant` | Financiaciones con garantías preferidas A y B | % |
| `com_part` | Cartera comercial / financiaciones | % |
| `con_part` | Cartera de consumo / financiaciones | % |
| `cac_part` | Cartera comercial asimilable a consumo / financiaciones | % |
| `com_garant` | Cartera comercial con garantías preferidas A y B | % |
| `con_garant` | Cartera de consumo con garantías preferidas A y B | % |
| `cac_garant` | Cartera asimilable a consumo con garantías preferidas A y B | % |
| `com_s1`…`com_s5` | Cartera comercial en situación 1 a 5 | % |
| `con_s1`…`con_s5` | Cartera de consumo o vivienda en situación 1 a 5 | % |
| `cac_s1`…`cac_s5` | Cartera comercial asimilable a consumo en situación 1 a 5 | % |

| Situación | Nombre | Atraso |
|---|---|---|
| 1 | Normal | hasta 31 días |
| 2 | Seguimiento especial / riesgo bajo | 31 a 90 días |
| 3 | Con problemas / riesgo medio | 90 a 180 días |
| 4 | Alto riesgo de insolvencia | 180 días a 1 año |
| 5 | Irrecuperable | más de 1 año |

Los días de atraso son la referencia para la cartera de consumo o vivienda. La cartera comercial se clasifica principalmente por la capacidad de pago del deudor.

`tf_irregular` (s3 + s4 + s5) es un cálculo sobre la tabla de situación de deudores. Puede diferir levemente de `irr_tot`, que el BCRA calcula con otra base. Para "mora", usar `irr_tot`.

---

## Información adicional (BCRA · trimestral)

Cantidades (unidades).

| Campo | Qué es | Unidad |
|---|---|---|
| `cc` | Cuentas corrientes | cantidad |
| `cah` | Cuentas (cajas) de ahorro | cantidad |
| `cah_social` | Cajas de ahorro de ayuda social | cantidad |
| `cprev` | Cuentas previsionales | cantidad |
| `pf_ind` | Operaciones a plazo fijo de individuos | cantidad |
| `pf_emp` | Operaciones a plazo fijo de empresas | cantidad |
| `op_hip` | Operaciones de préstamos hipotecarios | cantidad |
| `op_prend` | Operaciones de préstamos prendarios | cantidad |
| `op_otros` | Operaciones de otros préstamos | cantidad |
| `emp` | Dotación de personal (empleados) | cantidad |
| `tit` | Titulares de tarjetas de crédito | cantidad |
| `pla` | Tarjetas de crédito (plásticos) | cantidad |
| `deb` | Tarjetas de débito | cantidad |

## Cuentas sueldo (BCRA · mensual)

| Campo | Qué es | Unidad |
|---|---|---|
| `remu` | Cuentas sueldo: cuentas con acreditación de remuneraciones | cantidad |
| `remu_emp` | Empresas que pagan sueldos por acreditación bancaria | cantidad |

## Sucursales y cajeros (BCRA · foto al mes de actualización)

| Campo | Qué es | Unidad |
|---|---|---|
| `sucursales` | Sucursales totales = plenas + operatoria específica + móviles (CALCULADO) | cantidad |
| `suc_plenas` | Sucursales plenas | cantidad |
| `suc_especificas` | Sucursales de operatoria específica | cantidad |
| `suc_moviles` | Sucursales móviles | cantidad |
| `dep_automatizadas` | Dependencias automatizadas | cantidad |
| `cajeros` | Cajeros automáticos (ATM) | cantidad |
| `terminales` | Terminales de autoservicio | cantidad |
| `puestos_promocion` | Puestos de promoción | cantidad |
| `agencias` | Agencias complementarias de servicios financieros | cantidad |
| `suc_exterior` | Sucursales en el exterior | cantidad |
| `of_representacion` | Oficinas de representación en el exterior | cantidad |

`--provincias` agrega el detalle por provincia con las mismas claves.

---

## Cálculos frecuentes (siempre aclararlos al responder)

| Cálculo | Fórmula | Cómo obtenerlo |
|---|---|---|
| Participación de mercado | valor de la entidad / total del sistema × 100 | `consultar_ranking.py CAMPO --participacion` |
| Plásticos por titular | `pla` / `tit` | `consultar_entidad.py X --campo pla tit` |
| Tarjetas de débito por caja de ahorro | `deb` / `cah` | ídem |
| Saldo promedio por caja de ahorro | `bCA` × 1.000.000 / `cah` | aclarar que `bCA` es mensual y `cah` trimestral: usar el mismo mes |
| Variación entre períodos | (valor final / valor inicial − 1) × 100; en indicadores %, diferencia en puntos | `--serie` o `consultar_historico.py` |
| Variación real (ajustada por inflación) | (1 + variación nominal) / (1 + inflación del período) − 1 | combinar con `consultar_ipc.py --acumulado --desde ... --hasta ...` |
| Ticket promedio | monto / cantidad de operaciones | `consultar_pagos.py` lo calcula |
| Inflación acumulada | índice final / índice del mes anterior al inicio − 1 | `consultar_ipc.py --acumulado` |

**Totales del sistema:** no sumar ni promediar entidades a mano. Usar el grupo `sistema` (o `publicos`, `privados`, `companias`, `top10`), que el BCRA publica ya agregado y ponderado. Si hace falta un agregado que el BCRA no publica (por ejemplo, "solo bancos" para un indicador en %), ponderar por la base correspondiente (mora por préstamos, ROE por patrimonio) y aclarar que es un cálculo propio.

---

## Inflación (INDEC · IPC Nacional · mensual)

En %. `consultar_ipc.py` devuelve variación mensual, interanual y acumulada del año.

| Serie (`--serie`) | Qué es |
|---|---|
| `nivel` | Nivel general: "la inflación" |
| `nucleo` | Núcleo: sin regulados ni estacionales (inflación de fondo) |
| `regulados` | Precios regulados o con alto componente impositivo (tarifas, combustibles, transporte) |
| `estacional` | Precios con estacionalidad (frutas, verduras, ropa, turismo) |
| `bienes`, `servicios` | Apertura por tipo |
| `01`…`12` o nombre | Divisiones: alimentos, bebidas alcohólicas, prendas, vivienda, equipamiento, salud, transporte, comunicación, recreación, educación, restaurantes, bienes y servicios varios |

Regiones (`--region`): Nacional (por defecto), GBA, Pampeana, Noreste, Noroeste, Cuyo, Patagonia.

## Medios de pago (BCRA · Pagos Minoristas · mensual)

Cantidad de operaciones y monto nominal en pesos (o en la moneda que indique la serie). `consultar_pagos.py --series` lista todas las series del último archivo. Principales:

| Hoja | Series |
|---|---|
| Cheques | Cheques compensados, físicos, ECHEQ (pesos y dólares), rechazados, rechazados sin fondos |
| Transferencias de fondos | Transferencias inmediatas push y pull, pagos con transferencia (QR interoperable), alto valor, en lote |
| Series push apertura | Transferencias push por canal (cajero, banca empresas, home banking, mobile banking) |
| Tarjetas | Tarjetas de crédito, débito (pesos y dólares), prepagas |
| TC Modalidad de pago | Crédito en un pago y en cuotas |
| Tarjeta de credito por canal | e-commerce, POS+QR, débito automático, otros |
| Transporte | Tarjetas prepagas de transporte, viajes con QR |
| Resto | Débitos directos, débito inmediato (DEBIN), extracciones, depósitos en cajeros, plazos fijos compensados, MEP, factura de crédito electrónica MiPyME (FCEM), POS activos |
| Cuentas de pago y fondos invert | Cuentas de pago con saldo (billeteras) y saldos invertidos en fondos |

Cada hoja tiene su propio rezago: el último mes puede variar por serie.

---

## Identificación de entidades

Los scripts resuelven nombres sin distinguir mayúsculas ni acentos, ignoran "Banco", "S.A.", "S.A.U." y aceptan el código del BCRA. Alias frecuentes:

| El usuario dice | Entidad | Código |
|---|---|---|
| Galicia | Banco de Galicia y Buenos Aires S.A. | 7 |
| Nación, BNA | Banco de la Nación Argentina | 11 |
| Provincia, Bapro | Banco de la Provincia de Buenos Aires | 14 |
| ICBC | Industrial and Commercial Bank of China (Argentina) | 15 |
| Citi | Citibank N.A. | 16 |
| BBVA, Francés | Banco BBVA Argentina S.A. | 17 |
| Bancor, Córdoba | Banco de la Provincia de Córdoba S.A. | 20 |
| Supervielle | Banco Supervielle S.A. | 27 |
| Ciudad | Banco de la Ciudad de Buenos Aires | 29 |
| Patagonia | Banco Patagonia S.A. | 34 |
| Hipotecario | Banco Hipotecario S.A. | 44 |
| Santander | Banco Santander Argentina S.A. | 72 |
| Credicoop | Banco Credicoop Cooperativo Limitado | 191 |
| Macro | Banco Macro S.A. | 285 |
| Comafi | Banco Comafi S.A. | 299 |
| BICE | Banco de Inversión y Comercio Exterior | 300 |
| BIND, Industrial | Banco Industrial S.A. | 322 |
| Santa Fe | Nuevo Banco de Santa Fe S.A. | 330 |
| Carrefour, Servicios Financieros | Banco de Servicios Financieros (Carrefour) | 332 |
| Ualá | Ualá Bank S.A.U. | 384 |
| Brubank | Brubank S.A.U. | 143 |
| Naranja X | Naranja Digital Compañía Financiera S.A. | 45030 |
| Reba | Reba Compañía Financiera S.A. | 45072 |

Grupos: `sistema` (todo el sistema financiero: bancos y compañías financieras), `publicos`, `privados`, `companias` (compañías financieras), `top10` (10 primeros bancos privados).

Si el nombre coincide con varias entidades, el script devuelve `candidatos`: preguntar al usuario. Si no coincide con ninguna, la entidad no es un banco ni una compañía financiera de la nómina del BCRA (las billeteras virtuales y otros proveedores de pago no están): decirlo.
