# Contexto argentino para leer métricas bancarias

Lo que un analista con experiencia sabe antes de mirar un gráfico. Los hechos posteriores a 2025 y cualquier fecha exacta que vaya a una respuesta conviene confirmarlos con los datos (los saltos se ven en el panel) o con una búsqueda web.

## Índice
1. Cómo leer los números
2. Regímenes 2014-2026 y cómo tratarlos
3. Estructura del sistema
4. Reglas que moldean las oportunidades
5. Qué datos no existen y qué proxies usar

---

## 1. Cómo leer los números

- **Contabilidad por inflación.** Desde los ejercicios que empiezan en enero de 2020, los bancos reexpresan sus estados contables por inflación (NIC 29, Com. "A" 6651 del BCRA). Cada balance está en moneda de su fecha de cierre. `bRM` es el resultado monetario: la pérdida (o ganancia) por mantener activos o pasivos monetarios con inflación. En bancos con muchos depósitos a la vista suele ser muy negativo, y es la contracara de un fondeo barato.
- **Antes de 2020**, los resultados eran nominales: el ROE de 2016-2019 no es comparable con el de 2020 en adelante.
- **Partidas en dólares.** Préstamos, depósitos y títulos en moneda extranjera se valúan en pesos al tipo de cambio oficial de referencia. Una devaluación los agranda sin negocio nuevo.
- **Tasas implícitas** (`tasa_prest`, `tasa_dep`): son cocientes contables (intereses sobre saldos promedio), no tasas de mercado. Sirven para comparar bancos entre sí, no para comparar con la BADLAR.
- **"Billón"** = un millón de millones (10¹²). Los balances del panel están en millones de pesos: 40.000.000 millones = 40 billones.
- **Rezago.** La información por entidad sale con unos 3 meses de rezago (4 en la trimestral). La macro va más adelantada. Al presentar, decí "a julio de 2026", no "hoy".

## 2. Regímenes 2014-2026 y cómo tratarlos

| Período | Qué pasó | Qué le hace a las métricas | Cómo tratarlo |
|---|---|---|---|
| 2014-2015 | Cepo cambiario (desde fines de 2011), devaluación de enero de 2014, tasas reguladas (topes a préstamos, mínimos a plazo fijo) | Spreads administrados; crédito en dólares casi nulo | El IPC nacional no existe: el deflactor es un empalme con CER. Usar con cautela |
| Dic-2015 a 2017 | Unificación cambiaria, metas de inflación, LEBAC; en 2016 nace la UVA | Boom de hipotecarios UVA (2017 a mediados de 2018) y de personales; vuelve el crédito en dólares | Buen período para elasticidades "normales" de crédito |
| 2018 | Crisis cambiaria (abril a septiembre), acuerdo con el FMI, tasas por encima de 60 %, LEBAC reemplazadas por LELIQ | Se frena el crédito; sube la mora con rezago; los hipotecarios UVA se paran | Quiebre: no mezclar 2017 con 2018-2019 sin aclararlo |
| 2019 | Shock de las PASO (agosto), salida de depósitos en dólares, vuelve el cepo (septiembre) | Caen fuerte los depósitos en dólares; crédito real en caída | Salto cambiario: valuación en pesos |
| 2020 | Pandemia: créditos a tasa subsidiada (MiPyME 24 %, tasa 0 a monotributistas), congelamiento de cuotas, **flexibilización transitoria de la clasificación de deudores** | La mora de 2020 y del primer trimestre de 2021 está **subestimada**. El salto de abril-mayo de 2021 es en buena parte normalización | No leer la baja de mora de 2020 como mejora ni el salto de 2021 como deterioro súbito |
| 2021-2023 | Inflación en aceleración (cerca de 50 %, 95 % y 211 % anual), tasa mínima de plazo fijo, LELIQ y pases con el BCRA | Crédito privado real en caída; títulos y BCRA dominan el activo; ROE sostenido por la tenencia de títulos | Margen financiero poco ligado al negocio con clientes |
| Dic-2023 | Devaluación (el oficial pasa de unos 366 a 800 $/USD), *crawling peg* de 2 % mensual, liberación de tasas, LELIQ reemplazadas por pases pasivos; inflación de 25,5 % ese mes | Salto en pesos de todo lo dolarizado; depósitos reales en mínimos | Excluir dic-2023 de las tasas de cambio mensuales o tratarlo como *dummy* |
| 2024 | Desinflación (117,8 % anual, con mensuales que bajan de 20 % a cerca de 2-3 %); fin de los pases pasivos y nacen las LEFI (julio); blanqueo (desde agosto); vuelven los hipotecarios UVA (desde abril) | Boom de crédito en pesos (personales, tarjetas, prendarios); suben fuerte los depósitos en dólares; los títulos pierden peso en el activo | Crecimientos reales muy altos desde una base baja: no extrapolar |
| 2025 | Crawling de 1 % (febrero); acuerdo con el FMI y salida del cepo para personas, con bandas cambiarias (abril); fin de las LEFI (julio) y alta volatilidad de tasas y encajes; elecciones legislativas (octubre); inflación de 31,5 % anual | La mora de consumo sube con fuerza (la cosecha del boom de 2024 madura con tasas reales altas); se desacelera el crédito | Período clave para la sensibilidad de la mora al costo del crédito y al salario real |
| 2026 | Confirmar con datos y con una búsqueda web | El panel muestra el nivel y la tendencia de la mora, del crédito y del ROE | Toda afirmación sobre 2026 sale del panel, no de memoria |

Inflación anual de control (INDEC, nivel general): 2024 = 117,8 %; 2025 = 31,5 %.

## 3. Estructura del sistema

- **Unas 60 entidades bancarias y una docena de compañías financieras.** El agregado `sistema` incluye las dos.
- **Bancos públicos.** Nación y Provincia de Buenos Aires son los más grandes; Ciudad y los bancos provinciales (Córdoba, Neuquén, Chubut, Santa Cruz, La Pampa, entre otros) completan el grupo. Varios bancos provinciales privados o mixtos (Macro en el NOA y el NEA, Santa Fe y Entre Ríos) son **agentes financieros** de su provincia: tienen las cuentas sueldo de los estatales, una base cautiva para préstamos de consumo.
- **Grandes privados:** Galicia, Santander, BBVA, Macro, ICBC, Supervielle, Patagonia, Credicoop (cooperativo, fuerte en pymes), Hipotecario, Comafi, Industrial (BIND), entre otros.
- **Digitales:** Brubank, Ualá Bank, Naranja X (compañía financiera) y otros que crecen desde una base chica: cuotas que se multiplican pero todavía pesan poco.
- **Billeteras y proveedores de pago** (por ejemplo, Mercado Pago) **no están** en la nómina de entidades financieras: no aparecen en el panel, aunque compiten fuerte en cuentas, pagos y crédito al consumo. Sus saldos aparecen agregados en el Informe de Pagos Minoristas (hoja "Cuentas de pago"; bcra-oraculo: `consultar_pagos.py`).
- **Fusiones y adquisiciones recientes** que mueven cuotas de golpe: Macro compró Itaú Argentina (acuerdo en agosto de 2023; la integración al balance de Macro fue posterior) y Galicia compró HSBC Argentina (cierre el 6 de diciembre de 2024; la fusión de ambos bancos vino después). Mientras la entidad comprada reporta por separado, la suma "grupo" no aparece en el panel; cuando se fusiona, la cuota salta. Ante cualquier salto persistente de activo que marque `calidad`, buscar la operación y su fecha antes de interpretar. Códigos BCRA de las absorbidas: **259** (Banco BMA, ex Itaú; último reporte propio en oct-2024, luego en Macro) y **150** (HSBC Bank Argentina, luego Banco GGAL; último reporte en may-2025, luego en Galicia). Con `panel.py --historicas` aparecen con tipo "historica" y `analizar.py proforma --fusion Macro=259 Galicia=150` las suma hacia atrás.
- **Rasgos estructurales:** crédito al sector privado muy bajo en relación al PBI (oportunidad de largo plazo), economía bimonetaria, cuenta sueldo gratuita y portable (ancla de la relación con el cliente), transferencias inmediatas y QR interoperable que comoditizan los pagos, ECHEQ y factura de crédito electrónica para pymes.

## 4. Reglas que moldean las oportunidades

- **Crédito en dólares:** solo para quienes tienen ingresos en dólares (exportadores, cadenas vinculadas). La oportunidad en dólares es comercio exterior y agro, no consumo.
- **Encajes y liquidez:** cuando el BCRA sube encajes o cambia los instrumentos de liquidez (LELIQ, pases, LEFI), cambia el costo de oportunidad de prestar. Las variaciones de `titulos_activo` y `liq_amplia` muchas veces son regulatorias, no estratégicas.
- **Clasificación de deudores y previsiones:** la mora (situación 3 a 5) sigue días de atraso en consumo. Los cambios transitorios de criterio (2020-2021) distorsionan las series.
- **Topes y programas:** topes a la tasa de tarjetas y programas de cuotas (por ejemplo, "Ahora 12") cambiaron la rentabilidad de tarjetas en distintos años. Si una serie de tarjetas salta, revisar si cambió la regla.
- **Cuenta sueldo:** el trabajador puede portarla a otro banco. Una cuota de cuentas sueldo alta no es para siempre: hay que monetizarla con producto.

## 5. Qué datos no existen y qué proxies usar

| No existe por banco | Proxy disponible |
|---|---|
| Cantidad de clientes | Cajas de ahorro (`cah`), titulares de tarjetas (`tit`), cuentas sueldo (`remu`) |
| Tasa por producto | Tasa implícita total (`tasa_prest`); tasas de mercado por línea a nivel sistema (`macro_ar.py`) |
| Mora por producto | Mora de consumo y comercial (`irr_cons`, `irr_com`); situación por cartera (`con_s*`, `com_s*`) |
| Crédito por provincia y banco | Sucursales por provincia (bcra-oraculo: `consultar_entidad.py X --seccion sucursales --provincias`) |
| Originación (flujo) | Variación del stock real (aproximación; incluye cancelaciones y castigos) |
| Tarjetas en el balance | `mix_otros` (incluye tarjetas y otros) |

Si el usuario pide algo de esta tabla, decí que no se publica y ofrecé el proxy, aclarando qué captura y qué no.
