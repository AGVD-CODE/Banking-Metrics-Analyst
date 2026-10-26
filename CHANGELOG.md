# Changelog

Cambios del skill `estratega-bancario`. Las versiones siguen [versionado semántico](https://semver.org/lang/es/) según su contrato ([`references/contrato.md`](skill/estratega-bancario/references/contrato.md)).

## [1.3.0] — 2026-10-25

Suma lo mejor de BCRA-Oraculo-Pro: un resumen automático del mes y un filtro de riesgo con el skill nuevo riesgo-bancario. Además corrige tres puntos débiles que encontró una revisión independiente.

### Agregado

- **`analizar.py novedades`:** lo más importante del mes, automático, como respuesta rápida sin el flujo completo. Incluye:
  - récords de la serie del sistema;
  - movimientos fuera de lo habitual;
  - las entidades grandes cuya mora más subió;
  - quién ganó y perdió más cuota, avisando si el cambio se concentró en un mes;
  - crecimiento real de préstamos y depósitos;
  - las alertas de cartera de riesgo-bancario, si está instalado.
- **`scripts/filtro_riesgo.py`:** usa riesgo-bancario 1.x, opcional, para pasar las oportunidades por salud, estrés y alertas de cartera. Si falta, explica qué instalar y cómo seguir. Se usa en el paso 6 de `SKILL.md`.
- **`correlacion`:** los pares que se mueven juntos por construcción contable (mora y cobertura, ROE y ROA, un saldo y su cuota) salen de la lista de hallazgos y se informan aparte, en `relaciones_contables`.

### Corregido

- **`--excluir` se aplica antes de transformar** en `correlacion` y `sensibilidad`. Antes, una variación de 12 meses que comparaba contra un mes excluido (por ejemplo, el alivio COVID) seguía entrando al análisis. Se aplica a las series bancarias y no a las macro.
- **`anomalias`:** el total del sistema ya no se cuenta como un par más al calcular el z frente a los pares. Se sigue evaluando contra su propia historia.
- **Mix de cartera y de depósitos:** un producto vacío (`---`) en un banco que sí informa su cartera total cuenta como 0 %. Antes, ese banco quedaba afuera de la mediana de pares y la inflaba. Por ejemplo, la mediana de prendarios de los 10 mayores bajaba de 4,2 % a 3,1 % y la de todos los bancos, de 1,7 % a 0,3 %.

## [1.2.0] — 2026-10-25

El revisor independiente pasa a ser un skill aparte, **revisor-independiente**, que cualquier skill puede usar.

### Por qué

- **El método de revisión no es bancario.** Recalcular los números clave, controlar unidades y coherencia, calificar la evidencia y la segunda ronda corta sirven para cualquier análisis con cifras. Separado, se mejora una vez y lo aprovechan todos los skills.
- **Lo bancario queda acá.** El estratega le pasa al revisor su lista de control del dominio.

### Cambió

- **Requiere el skill revisor-independiente 1.0 o posterior, misma versión mayor (1.x),** instalado aparte. El paso 7 de `SKILL.md` lo usa con la lista bancaria.
- **Si el revisor falta o no es compatible,** `scripts/revisor.py` lo dice, explica qué instalar y propone una revisión reducida con la lista bancaria, que la respuesta tiene que declarar.

### Agregado

- `scripts/revisor.py`: ubica el revisor (`REVISOR_DIR`, la carpeta de skills donde está instalado el estratega, `~/.claude/skills/` y las carpetas de skills de Claude), lee su `VERSION` y devuelve las rutas de sus instrucciones y de las dos listas.
- `references/revision_bancaria.md`: la lista de control bancaria (pesos constantes, fusiones, quiebres de régimen, NIC 29, mediana contra ponderado, mora diluida, moneda de la base, costos únicos, fair share).

### Quitado

- `references/revisor.md`. El método general está en revisor-independiente, y lo bancario, en `references/revision_bancaria.md`.

## [1.1.0] — 2026-10-25

Pasa a usar la capa de datos instalada en lugar de una copia propia.

### Por qué

- **Que cada skill se mejore por su cuenta.** Con una copia de `bcra_comun.py`, las correcciones de bcra-oraculo no llegaban al estratega hasta volver a copiar.
- **Que cada capa haga lo suyo.** Armar paneles es trabajo de datos y ahora lo hace bcra-oraculo 2.1 (`consultar_panel.py`). Lo puede usar cualquier skill futuro.

### Cambió

- **Requiere el skill bcra-oraculo 2.1 o posterior, misma versión mayor (2.x),** instalado aparte.
  - `scripts/_comun.py` lo busca en este orden: `BCRA_ORACULO_DIR`, la carpeta de skills donde está instalado el estratega, `~/.claude/skills/` y las carpetas de skills de Claude.
  - Lee su `VERSION` sin importarlo y frena con un mensaje claro si no es compatible.
- **`scripts/panel.py` reemplaza a `panel_bcra.py`.** Acepta los mismos argumentos y le delega el trabajo a `consultar_panel.py` del oráculo. El CSV es idéntico.
- `analizar.py` importa del oráculo solo su interfaz pública: `CAMPOS`, `describir`, `GRUPOS`, `ALIAS`, `ALIAS_GRUPO`, `VACIAS` y `norm`.

### Quitado

- `scripts/bcra_comun.py` (copia), `scripts/panel_bcra.py`, `references/diccionario_bcra.md` y `references/fuentes_bcra.md`. Las referencias equivalentes están en bcra-oraculo.

### Agregado

- `references/contrato.md`: qué necesita el skill, qué entrega (archivos de `trabajo/` y JSON de cada análisis) y cómo se versiona.
- Constante `VERSION = '1.1.0'` en `scripts/_comun.py`.

## [1.0.0] — 2026-10-25

Primera versión publicada.

- Analista estratégico con flujo de encuadre, hipótesis, datos, calidad, análisis, triangulación, dimensionamiento, revisión independiente y respuesta con gráficos.
- 10 análisis: `preparar`, `calidad`, `proforma`, `cuotas` (con mapa por producto), `brechas`, `rentabilidad`, `correlacion`, `segmentar`, `sensibilidad` (con efecto cosecha) y `anomalias`, más gráficos exploratorios.
- Copia incluida de `bcra_comun.py` (bcra-oraculo 2.0.0) para ser autocontenido.
