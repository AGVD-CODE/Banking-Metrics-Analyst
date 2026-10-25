# Playbook de oportunidades: de patrón en los datos a negocio

## Índice
1. Hipótesis frecuentes y cómo probarlas
2. Cómo dimensionar
3. Cómo priorizar
4. Ficha de oportunidad
5. Errores que hacen perder credibilidad ante un comité

---

## 1. Hipótesis frecuentes y cómo probarlas

Cada patrón incluye la señal en los datos, el análisis que la confirma y la oportunidad típica. Elegí las que encajan con la pregunta y con el banco foco.

**A. Base cautiva sin monetizar**
- Señal: cuota de cuentas sueldo (`cuota_remu`) o de cajas de ahorro (`cuota_cah`) mayor que la cuota de personales (`cuota_bPers`) o de tarjetas (`cuota_pla`); `pers_por_remu` bajo la mediana.
- Confirmar: `brechas` (fair share y penetración) y `cuotas` de `bPers` (¿la brecha se cierra o se abre?).
- Oportunidad: venta cruzada a la base de sueldos (preaprobados, adelanto de sueldo, tarjeta). Es el crecimiento más barato porque el cliente ya está.
- Riesgo: si la mora de consumo del foco ya está alta, la palanca es mejorar el scoring dentro de la base, no empujar volumen.

**A2. Base de jubilados**
- Señal: cuota de cuentas previsionales (`cuota_cprev`) mayor que la de personales; mora de consumo más baja que la de sus pares.
- Confirmar: `brechas` (fair share `cprev → bPers`) y `correlacion --modo transversal --variables cuota_cprev irr_cons`.
- Oportunidad: préstamos a jubilados con cobro sobre el haber (riesgo bajo, ticket chico). No hay datos por banco del destino del crédito: presentalo como hipótesis a validar con la cartera interna.

**B. Fondeo barato ocioso**
- Señal: `mix_ca` y `mix_cc` altos (fondeo a la vista barato), `ld_ratio` bajo y `titulos_activo` alto.
- Confirmar: `brechas`, más `grafico dispersion --x ld_ratio --y roe`.
- Oportunidad: transformar liquidez en crédito a empresas (documentos, adelantos) o a consumo. Cuantificar el spread que se deja en títulos.
- Riesgo: el regulador puede estar empujando esa tenencia (encajes integrables con títulos). Revisar el contexto.

**C. Precio mal puesto**
- Señal: `spread` bajo frente a pares con mora parecida (se deja margen) o `spread` alto con mora baja (nicho rentable que conviene defender o escalar).
- Confirmar: `correlacion --modo transversal --variables spread irr_tot roe` y `brechas`.
- Oportunidad: *repricing* selectivo o expansión del nicho.
- Aproximación del retorno ajustado por riesgo: `tasa_prest` − `tasa_dep` − `costo_riesgo` − `absorc_gastos` (todo en %, aproximado).

**D. Riesgo que se viene**
- Señal: mora que sube de forma **idiosincrática** (`anomalias`: z alto contra pares), mucha sensibilidad de la mora al salario real (`sensibilidad`), efecto cosecha alto (`sensibilidad --x-propias bPers_ia:nivel`) o situación 2 (`con_s2`) en alza. Compará `irr_cons_sin_dilucion`: un banco que creció mucho puede tener la peor originación con la mora "publicada" más baja.
- Oportunidad defensiva: frenar originación en los segmentos más sensibles, reforzar cobranzas y reprecificar. La oportunidad ofensiva es la contracara: si el foco es **menos** sensible que sus pares, puede ganar cuota cuando los demás se retiran.

**E. Timing del ciclo**
- Señal: productos con alta elasticidad al salario real o a la tasa real (`correlacion` temporal y `sensibilidad` con la métrica de crecimiento como y).
- Oportunidad: acelerar originación cuando el indicador líder gira (por ejemplo, salario real en alza con 0 a 3 meses de rezago para personales) y frenar antes de que madure la mora.

**F. Momentum de cuota y competidores en retirada**
- Señal: en `cuotas`, bancos grandes con pendiente negativa en un producto cuyo mercado crece en términos reales.
- Oportunidad: capturar clientes desatendidos (campañas de portabilidad, ofertas a sus segmentos). Identificar qué banco cede y en qué producto.

**G. Modelo de negocio ganador**
- Señal: en `segmentar`, un segmento con ROE alto y mora baja.
- Oportunidad: incorporar los rasgos de ese modelo (por ejemplo, más fondeo transaccional de empresas, más adelantos y documentos) o competir en ese nicho. Ojo: los rasgos van juntos, no se copian de a uno.

**G2. Rentabilidad: dónde se escapa**
- Señal: en `rentabilidad`, el componente con mayor brecha en pesos contra pares (gastos, incobrabilidad, comisiones o margen neto de inflación).
- Oportunidad: el plan se ordena solo. Si la brecha es de gastos, la palanca es escala o eficiencia; si es de margen neto de inflación, fondeo y precio; si es de incobrabilidad, riesgo. Un comité entiende mejor "nos faltan 2,6 puntos de activo en gastos, $225 mil millones por año" que diez ratios sueltos.

**H. Comisiones**
- Señal: `fee_ratio` o `cuota_bIS` por debajo de la cuota de activo.
- Oportunidad: paquetes, comercio exterior, *cash management*, adquirencia. En un contexto de desinflación, las comisiones reemplazan al margen por inflación.

**I. Eficiencia y canales**
- Señal: `dep_empleado` y `fin_empleado` bajos, `eficiencia` alta, muchas sucursales por depósito.
- Oportunidad: digitalización y redimensionamiento de red, o, al revés, red física subutilizada para originar más.

**J. Productos con viento a favor**
- Hipotecarios UVA (volvieron en 2024: mirar `cuota_bHip` y `bHip_ia`), prendarios (cruzar con producción y venta de autos), pymes (documentos, ECHEQ y factura de crédito en el Informe de Pagos Minoristas), agro y comercio exterior (dólares).

## 2. Cómo dimensionar

Siempre con supuestos explícitos y en pesos constantes de la base del panel.

| Tipo | Fórmula | Fuente en los scripts |
|---|---|---|
| *Fair share* | (cuota base − cuota objetivo) × total del sistema del objetivo | `brechas` → `oportunidades` |
| Brecha de mix | (mediana de pares − mix del foco) × préstamos privados del foco | `brechas` |
| Penetración | (mediana de pares − foco) × base del foco (cuentas sueldo, cajas de ahorro, titulares) | `brechas` |
| Crecimiento de mercado | stock de mercado × crecimiento real esperado × cuota objetivo | `cuotas` + supuesto de crecimiento |
| Recuperar cuota perdida | (cuota de referencia − cuota actual) × mercado actual | `cuotas` |

**Pasar de stock a resultado anual (aproximación):** stock incremental × (tasa del producto − costo de fondeo − pérdida esperada − costo operativo).
- Tasa del producto: tasa de mercado de la línea (`macro_ar.py`, por ejemplo `tasa_personales`) o `tasa_prest` del foco.
- Costo de fondeo: `tasa_dep` del foco.
- Pérdida esperada: `costo_riesgo` del foco o del segmento.
- Costo operativo: `absorc_gastos`.

Aclarar siempre que es un orden de magnitud.

**Escenarios.** Presentá conservador (cerrar 25 % de la brecha), base (50 %) y optimista (100 %, que es la cota). Nunca presentes la cota como meta.

**Sin doble conteo.** Las brechas de *fair share* de personales y la de mix de personales miden lo mismo desde dos lados: elegí una.

## 3. Cómo priorizar

Puntuá cada oportunidad de 1 a 5 en:
- **Tamaño:** resultado anual estimado.
- **Evidencia:** robusta = 5, indicio = 3, hipótesis = 1.
- **Factibilidad:** capacidades, canales y sistemas del banco; regulación.
- **Riesgo:** mora, fondeo, reputación (5 = bajo riesgo).
- **Tiempo a impacto:** menos de 6 meses = 5.

Prioridad = tamaño × evidencia × factibilidad × riesgo × tiempo (o promedio ponderado, si el usuario prefiere). Separá *quick wins* (alta factibilidad, rápidas) de **apuestas** (grandes, inciertas). Un comité quiere ver las dos.

## 4. Ficha de oportunidad

Para cada oportunidad principal:

- **Qué:** el producto o segmento, y la acción.
- **Por qué ahora:** el dato y el contexto que la habilitan.
- **Tamaño:** stock y resultado anual, con escenarios y supuestos.
- **Evidencia:** análisis, robustez y qué la podría desmentir.
- **Cómo capturarla:** canal, oferta y precio.
- **Riesgos y mitigantes.**
- **KPI de seguimiento:** por ejemplo, cuota mensual de `bPers` del BCRA, `pers_por_remu` o mora de la cosecha.
- **Primer paso en 90 días:** piloto, segmento y meta medible.

## 5. Errores que hacen perder credibilidad ante un comité

- Presentar crecimientos nominales como si fueran reales.
- Leer como mérito comercial un salto que fue fusión, devaluación o error de carga.
- Llamar "oportunidad" a crecer en el segmento donde la mora ya se está disparando.
- Comparar contra pares que tienen otro modelo de negocio.
- Sumar oportunidades que se superponen.
- Decir "causa" con evidencia de correlación.
- Dar un número sin período, sin unidad o sin fuente.
- Usar datos de memoria en lugar de los que devolvieron los scripts.
