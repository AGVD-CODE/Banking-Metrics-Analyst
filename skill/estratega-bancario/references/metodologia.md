# Metodología: cómo correr, leer y defender cada análisis

## Índice
1. Preparar los datos (incluye fusiones y pro forma)
2. Cuotas de mercado y descomposición del crecimiento
3. Brechas contra pares y *fair share*
4. Árbol de rentabilidad
5. Correlación temporal
6. Correlación transversal
7. Segmentación de modelos de negocio
8. Sensibilidad macro y efecto cosecha
9. Anomalías
10. Checklist de robustez
11. Cómo escribir la fuerza de la evidencia

---

## 1. Preparar los datos

- **Pesos constantes.** `preparar --macro macro.csv` multiplica cada monto por IPC(base) / IPC(mes). La base por defecto es el último mes del panel; cambiala con `--base`. Antes de dic-2016 no hay IPC nacional: `macro_ar.py` empalma hacia atrás con el CER y lo avisa.
- **Resultados acumulados.** `bRes`, `bIF`, `bGA`, `bInc` y los demás resultados se acumulan desde enero. Para anualizar: valor × 12 / mes. `costo_riesgo` ya lo hace. Para comparar resultados entre bancos, usá el mismo mes del año.
- **Trimestrales.** `pla`, `tit`, `cah`, `cc`, `deb`, `emp`, `pf_*` y `op_*` solo tienen dato a fin de trimestre. Los cruces con datos mensuales usan el mismo mes (`brechas` y `cuotas` buscan el último período con dato).
- **Mix de cartera.** Los `mix_*` se calculan sobre préstamos al sector privado (`bPr_priv`). `mix_otros` es el resto: incluye tarjetas, porque el balance publicado no las abre.
- **Cuotas.** Se calculan sobre el agregado oficial del sistema (`AAA00`, que incluye compañías financieras). La suma de los bancos da un poco menos de 100 %.
- **Errores y fusiones.** Corré siempre `calidad`. Un pico aislado contamina cuotas, mix y crecimientos de ese mes: excluí ese período del análisis que lo use. Un `salto de cuota` que no se revierte suele ser una fusión: armá el panel con `--historicas`, sumá la absorbida con `proforma` y volvé a correr `preparar` y `calidad` (el salto tiene que desaparecer). En el pro forma, montos y cantidades se suman; mora y tasas se ponderan; los demás indicadores del BCRA de los meses previos quedan como los del absorbente (no los leas como pro forma).
- **Mora sin dilución.** Un banco que crece rápido baja su mora "por denominador": los préstamos nuevos todavía no tuvieron tiempo de caer. `irr_cons_sin_dilucion` divide la cartera irregular de hoy por la cartera de hace 12 meses. Para comparar la calidad de originación de un banco que crece con la de uno que se achica, usá esta versión.
- **Alivio COVID.** Entre abril de 2020 y marzo de 2022 la clasificación de deudores estuvo flexibilizada y la mora está subestimada. En análisis temporales de mora, usá `--excluir 2020-04:2022-03`.
- **Tipo de cambio.** Los saldos incluyen partidas en dólares valuadas en pesos. Si el período cruza una devaluación (dic-2023 y, en menor medida, los saltos de 2018, 2019 y 2025), una parte del "crecimiento real" es valuación. Para estimarla a nivel sistema, usá `prest_priv_usd` y `dep_priv_usd` de `macro_ar.py` por el tipo de cambio.

## 2. Cuotas de mercado y descomposición del crecimiento

Identidad: (1 + crecimiento del banco) = (1 + crecimiento del mercado) × (1 + efecto cuota).

- **Efecto mercado alto y efecto cuota cero:** el banco "surfeó" el mercado. No es mérito comercial.
- **Efecto cuota positivo con mercado en caída:** ganó clientes en la mala. Es la señal comercial más valiosa y suele ser más barato que crecer en la buena.
- **`pendiente_cuota_pp_mes_ult6`:** el momentum reciente. Un banco que ganó cuota en dos años pero hoy tiene pendiente negativa está perdiendo tracción.
- **HHI** (0 a 10.000) y **CR5**: concentración. HHI subiendo en un producto = los grandes se lo están quedando. Productos fragmentados (HHI < 1.000) dejan lugar para escalar.

Trampas: un banco con mucha cartera en dólares gana cuota "en pesos" cuando hay devaluación. Las adquisiciones mueven cuota de golpe. En productos chicos (prendarios, hipotecarios), un solo banco o un cambio de criterio contable mueve todo.

## 3. Brechas contra pares y *fair share*

- **Percentil** entre pares (0 = menor valor, 100 = mayor). `lectura` marca fortaleza o debilidad solo donde "mejor" tiene dirección clara (mora, ROE, eficiencia). El mix es una **elección de modelo**: no es ni bueno ni malo, pero sí revela dónde el banco eligió no jugar.
- **Elegir pares.** Por tamaño (`top10`) para un comité. Por modelo de negocio (los `pares_reales_por_modelo` de `segmentar`) para un diagnóstico justo. Pares mal elegidos producen brechas que no son oportunidades: comparar a Credicoop con Nación en hipotecarios no dice nada.
- ***Fair share*.** Si un banco tiene X % de las cuentas sueldo y menos de X % de los préstamos personales, hay base cautiva sin monetizar. El tamaño ((cuota base − cuota objetivo) × total del sistema) es una **cota superior**: supone que la base es igual de prestable que la del promedio.
- **Brecha de mix.** (mediana de pares − mix del foco) × cartera del foco = stock adicional si el banco tuviera el mix típico. Sirve para dimensionar, no como meta: el mix de los pares puede estar mal.
- **Penetración.** Por ejemplo, préstamos personales por cuenta sueldo, saldo por caja de ahorro o tarjetas por titular, frente a la mediana. Es la métrica más accionable: se mueve con campañas y con *pricing*.

## 4. Árbol de rentabilidad

`rentabilidad` descompone el ROA de los últimos 12 meses (pesos constantes, flujo sobre activo promedio) en: margen financiero, comisiones netas, cargo por incobrabilidad, gastos de administración, resultado monetario, impuesto a las ganancias y otros. El ROE es el resultado sobre el patrimonio promedio, y debería coincidir con el R1 que publica el BCRA (es un buen control).

- **Leer juntos margen financiero y resultado monetario** (`margen_neto_de_inflacion`). Con inflación, parte de los intereses compensa la pérdida por mantener activos monetarios. Un banco puede tener "menos margen" y a la vez "menos pérdida monetaria": la diferencia neta es la que importa.
- **La brecha en pesos** (`brecha_en_pesos`) dice cuánto resultado anual vale cerrar cada componente hasta la mediana de los pares. Es el puente natural a las oportunidades.
- **Por segmento** (`--segmentos`): el ROE **ponderado** (suma de resultados sobre suma de patrimonios) es lo que gana el modelo de negocio como un todo; el **mediano** describe al banco típico. Si difieren mucho, un banco grande domina el segmento: decilo.
- Cargos extraordinarios (indemnizaciones, ventas de cartera) distorsionan 12 meses. Si los ves en la prensa o en un salto de `bGA`, aclaralo y mostrá la brecha con y sin ese efecto si se puede.

## 5. Correlación temporal

**Para qué sirve:** detectar qué variable macro adelanta o acompaña a una métrica bancaria, y con cuántos meses.

- **Transformación.** `auto` o `ia`: diferencia de 12 meses en tasas y porcentajes, variación de 12 meses en montos e índices. Es robusta a la estacionalidad, pero las ventanas se solapan y el `n_efectivo` baja mucho. `mensual`: variaciones de un mes, con más potencia y más ruido estacional. **Conclusión firme = el mismo signo y orden de magnitud con las dos.** Sufijos por variable: `campo:nivel`, `campo:dif`, `campo:var`, `campo:mensual`.
- **Rezagos.** `rezago_meses = k` significa que la variable macro de hace k meses se asocia con la métrica de hoy. Ignorá rezagos sin mecanismo plausible. Referencias razonables: los depósitos reaccionan a la tasa real en 0 a 3 meses; la originación de crédito al salario real en 0 a 3; la mora a shocks de ingreso en 6 a 12 (lo que tarda una cartera en pasar a situación 3).
- **`n_efectivo`** corrige por autocorrelación (Bartlett). Si es menor a 15, el resultado es frágil aunque `r` sea alto.
- **`q`** (Benjamini-Hochberg) corrige por haber probado muchos pares y rezagos. q < 0,05 robusta; 0,05 a 0,2 indicio; más de 0,2 no concluyente.
- **Deflactor común.** Dos montos reales comparten el IPC: los meses de inflación alta bajan ambos. Repetí con `--controles inflacion_m:nivel` (correlación parcial). Si la relación se cae, era mecánica.
- **Historia.** Para temporal, usá un panel desde 2016 (`--desde 2016-01 --top 25`) o el sistema. Con menos de 5 años no hay suficientes observaciones independientes.
- **Regímenes.** Corré también sobre una sub-ventana (por ejemplo, filtrando el panel desde 2024) y compará. Un signo que cambia entre ventanas es una relación que depende del régimen: decilo así.

## 6. Correlación transversal

**Para qué sirve:** ver qué rasgos de modelo de negocio van juntos entre bancos (por ejemplo, más personales con más tasa y más mora).

- Spearman (por rangos): robusto a outliers y a relaciones no lineales. Con 40 a 60 bancos, |rho| < 0,3 suele ser ruido.
- `--ventana 3` promedia 3 meses para suavizar. `--min-cuota` saca bancos ínfimos.
- **Falacia ecológica:** que los bancos con más personales tengan más mora no dice que, dentro de un banco, más personales cause más mora.
- **Confusión por tamaño o por tipo:** públicos y privados difieren en todo. Si la relación importa, repetí con `--universo privados` o con un segmento de `segmentar`.

## 7. Segmentación de modelos de negocio

- **Variables.** Por defecto, solo estructura (mix de cartera y fondeo, intermediación, títulos, tamaño). El desempeño (ROE, mora, eficiencia) **no** entra al clustering: se reporta por segmento. Así la pregunta queda bien planteada: "¿qué modelo de negocio rinde más?".
- **Elegir k.** Se elige por silhouette. Si k = 2 gana por poco, se prefiere un k entre 3 y 6 casi igual de bueno, porque k = 2 suele separar solo grandes y chicos.
- **Calidad.** Silhouette mayor a 0,5 indica estructura clara, entre 0,25 y 0,5 razonable, menos de 0,25 débil (en bancos es lo habitual: decí que los segmentos son una simplificación útil). ARI con Ward mayor a 0,6 y estabilidad bootstrap mayor a 0,7 indican segmentos robustos. Si son bajos, presentá los segmentos como tendencias, no como grupos.
- **Nombrar los segmentos** con negocio, no con estadística. "Transaccional pyme" se entiende; "alto mix_cc, bajo ld_ratio" no.
- **Insights típicos:** qué segmento combina ROE alto con mora baja y qué rasgos lo explican; quiénes son los competidores reales del foco (`pares_reales_por_modelo`); bancos "en transición" (silhouette cerca de 0) que están cambiando de modelo.

## 8. Sensibilidad macro y efecto cosecha

**Modelo.** Para cada banco, la métrica transformada se regresiona contra variables macro transformadas, con el rezago indicado. Los errores son HAC (Newey-West), porque los residuos están autocorrelacionados. El panel con efectos fijos estima la respuesta promedio de los bancos, con errores agrupados por banco.

- **`beta`** = cambio en la métrica por unidad de cambio en la macro. **`beta_std`** permite comparar variables de distinta escala.
- **Ranking de betas:** quién es procíclico y quién es defensivo. Un banco con beta bajo en mora frente al salario real puede crecer a contraciclo.
- **VIF > 5:** las variables macro se pisan (por ejemplo, salario real y EMAE). No leas cada beta por separado: dejá una sola o reportá el efecto conjunto.
- **Signos contraintuitivos.** Por ejemplo, mora que sube después de que sube el salario real. No los descartes ni los inventes: buscá el mecanismo. Puede ser un boom de crédito que se origina con salarios en alza y madura en mora meses después (efecto cosecha), o un régimen distinto mezclado en la muestra.
- **Rezago.** Probá 0, 3, 6 y 9 meses y quedate con el que tenga mecanismo, no con el que dé el mejor p (y decí que probaste varios).
- **Mínimo:** 36 observaciones por banco para algo publicable. Con menos, solo el panel.
- **Efecto cosecha** (`--x-propias bPers_ia:nivel --rezago 12`): el crecimiento real del crédito de cada banco como regresor de su propia mora futura. Suele ser el predictor más fuerte de la mora de consumo, más que cualquier variable macro, y separa a los bancos que crecieron con disciplina de los que compraron volumen. Probá rezagos de 9 a 15 meses.
- **Indicador temprano:** la situación 2 de consumo (`con_s2`, 31 a 90 días de atraso) anticipa la mora (situación 3 en adelante) en 1 a 3 meses. Si `con_s2` baja mientras la mora sigue subiendo, el pico puede estar cerca.
- **Ventanas:** `--desde`, `--hasta` y `--excluir` permiten estimar por régimen (por ejemplo, 2017-2019 frente a 2023-2026) y comparar betas.

## 9. Anomalías

- **z robusto** (mediana y MAD) del último cambio contra la historia propia y contra los pares. |z| > 2 llamativo; > 3 raro.
- **Naturaleza:** *sistémica* (inusual para el banco, pero todos se mueven igual: es el ciclo) frente a *idiosincrática* (el banco se despega de sus pares: estrategia, problema o error de datos). Las idiosincráticas son las que generan insights de negocio.
- **`p_quiebre_nivel` < 0,05:** el nivel de los últimos 6 meses difiere del de los 12 anteriores.
- Una anomalía es una **pregunta**, no una respuesta. Investigala con `cuotas`, `brechas`, `grafico linea` y contexto antes de presentarla.

## 10. Checklist de robustez (antes de presentar un insight)

- [ ] Los montos están en pesos constantes y lo dice la respuesta.
- [ ] `calidad` no marca picos ni saltos en las celdas que sostienen el hallazgo, y las fusiones del período están en pro forma.
- [ ] El período no cruza una devaluación sin aclararlo, o el efecto es de un orden de magnitud mayor.
- [ ] Se mantiene con otra ventana o con otra transformación.
- [ ] No lo explica el tamaño (probado con `topN` o `--min-cuota`).
- [ ] Hay mecanismo, y la explicación alternativa está dicha.
- [ ] El número que va al titular es el que imprimió el script, con período y unidad.

## 11. Cómo escribir la fuerza de la evidencia

| Evidencia | Cómo decirlo |
|---|---|
| q < 0,05, consistente entre ventanas, con mecanismo | "La relación es robusta: ..." |
| q entre 0,05 y 0,2, o consistente solo en una ventana | "Hay indicios de que ..." |
| q > 0,2 o n efectivo < 15 | "Los datos no alcanzan para afirmar ..." |
| Un solo banco o un solo mes | "Es un caso puntual que conviene seguir: ..." |

Nunca uses "causa", "provoca" o "determina" con evidencia correlacional. Decí "se asocia", "acompaña" o "anticipa".
