# Lista de control bancaria (para el revisor)

Es la lista del dominio que estratega-bancario le pasa al skill **revisor-independiente** (sección C de su lista general). Junta los errores típicos de un análisis de bancos argentinos con datos del BCRA. Las reglas completas están en `SKILL.md` ("Reglas de rigor") y en `metodologia.md`.

## Dónde están los datos

- **Paneles:**
  - `trabajo/panel*.csv` es nominal, en millones de pesos corrientes.
  - `trabajo/analitico*.csv` está en pesos constantes y su `.meta.json` dice el mes base.
  - `trabajo/macro.csv` trae las series macro.
- **Análisis:** el JSON de cada comando de `analizar.py` está en `trabajo/<análisis>.json` y su detalle, en `trabajo/out/*.csv`.
- **Filas:** una por `periodo` y `codigo`. Los agregados oficiales tienen códigos `AAA00` (sistema), `AAA10` (públicos), `AAA20` (privados) y `AAA50` (10 primeros privados). Las entidades ya cerradas tienen `tipo` = `historica`.

## Rigor

- **Montos en el tiempo, en pesos constantes,** y el texto dice de qué mes. Comparar montos de distintos meses en pesos corrientes es un crítico.
- **Fusiones en pro forma,** o la respuesta explica por qué no hace falta. Si no, el comprador "gana" cuota el mes de la integración:
  - Itaú, luego BMA (código 259), en Macro: último reporte oct-2024;
  - HSBC, luego GGAL (código 150), en Galicia: último reporte may-2025.
- **Quiebres de régimen:** si el período cruza la devaluación de dic-2023, el blanqueo de sep-2024 o el alivio COVID (2020-04 a 2022-03), la respuesta lo aclara. Esos meses inflan en pesos todo lo que está en dólares y reordenan cuotas de depósitos según cuánto dólar tiene cada banco.
- **Resultados acumulados del ejercicio** (bRes, bIF, bInc, bGA, bRM, etc.): no se comparan meses de distintos ejercicios como si fueran flujos mensuales. Para rentabilidad se usan los últimos 12 meses.
- **Ajuste por inflación contable desde 2020 (NIC 29):** el margen financiero se lee junto con el resultado monetario (`margen_neto_de_inflacion`).
- **Mediana y ponderado:** "el segmento X rinde más" vale con la mediana y con el promedio ponderado por activo, o la diferencia se dice.
- **Mora diluida:** el banco que crece rápido baja su mora sin mejorar la cartera. Mirar `irr_cons_sin_dilucion` antes de elogiar una mora baja.
- **Estadística:** las correlaciones temporales se calculan sobre variaciones y no sobre niveles, con n efectivo y q-valor. Los rezagos se informan como rango si dependen de la especificación.
- **Qué es un "banco":** las compañías financieras y las entidades chicas no se mezclan con los bancos sin aclararlo.

## Negocio

- **Cada oportunidad tiene tamaño en stock y en resultado anual,** con supuestos y escenarios (25, 50 y 100 % de la brecha) y sin doble conteo entre oportunidades.
- **Moneda de la base:** los saldos del balance mezclan pesos y dólares (depósitos, préstamos, títulos). Aplicar una tasa en pesos a un saldo que es en buena parte en dólares es un crítico.
- **Sin costos únicos tomados como estructurales:** indemnizaciones, cargos extraordinarios, ganancias por venta de activos.
- **Dentro de los límites que la propia respuesta recomienda:** topes de crecimiento, apetito de riesgo, capacidad de fondeo.
- **Las oportunidades que crecen donde la mora sube** dicen el riesgo y un control.
- **El fair share se calcula sobre la base de clientes correcta:** cuentas sueldo (`remu`), cuentas previsionales (`cprev`, jubilados), cajas de ahorro (`cah`) o titulares de tarjeta (`tit`). Son datos trimestrales: usar el mismo mes que el saldo.
