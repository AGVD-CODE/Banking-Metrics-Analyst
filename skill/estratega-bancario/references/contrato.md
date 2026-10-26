# Contrato de estratega-bancario

Qué necesita este skill, qué entrega y cómo se versiona. Sirve para construir otros skills encima (por ejemplo, uno que arme la presentación para el directorio) o debajo (otra fuente de datos), sin depender de su interior.

Versión del skill: **1.3.0** (constante `VERSION` en `scripts/_comun.py`). Sigue versionado semántico: si cambia algo de lo que figura en este documento (nombres de comandos, columnas, claves del JSON), sube la versión mayor.

## Depende de

| Skill | Versión | Para qué | Cómo se usa |
|---|---|---|---|
| `bcra-oraculo` | 2.1 o posterior, misma mayor (2.x) | Panel de entidades del BCRA (`consultar_panel.py`) y metadatos de campos | `scripts/panel.py` lo ubica, controla la versión y le pasa los argumentos. `analizar.py` importa solo su interfaz pública: `CAMPOS`, `describir`, `GRUPOS`, `ALIAS`, `ALIAS_GRUPO`, `VACIAS` y `norm` |
| `riesgo-bancario` (opcional) | 1.0 o posterior, misma mayor (1.x) | Filtro de riesgo de las oportunidades (salud, estrés, alertas de cartera) y alertas en `novedades` | `scripts/filtro_riesgo.py` lo ubica, controla su `VERSION` y le pasa los argumentos. Si falta, el skill sigue y lo declara |
| `revisor-independiente` | 1.0 o posterior, misma mayor (1.x) | Revisión de cada análisis antes de entregarlo | `scripts/revisor.py` lo ubica, controla la versión (su archivo `VERSION`) y devuelve las rutas de sus instrucciones. Este skill le pasa como lista del dominio `references/revision_bancaria.md` |

Si el oráculo falta o su versión no es compatible, `panel.py` y `analizar.py` terminan con un JSON que explica qué instalar. Nunca siguen con datos de otra versión. Si falta el revisor, `revisor.py` explica qué instalar y propone una revisión reducida con la lista bancaria, que la respuesta tiene que declarar.

## Entradas

- Una pregunta de negocio sobre bancos argentinos, en lenguaje natural.
- Opcionales: banco foco, pares, horizonte y destino (comité, consultoría, plan anual).

## Salidas

**Para el usuario:** la respuesta con el formato de `SKILL.md` ("Formato de respuesta"): titular, insights, oportunidades priorizadas, gráficos, límites y fuentes.

**Para otros skills o agentes:** la carpeta de trabajo `trabajo/`.

| Archivo | Qué es |
|---|---|
| `panel*.csv` | Panel nominal del oráculo: `periodo`, `codigo`, `entidad`, `tipo` y un campo por columna |
| `macro.csv` | Series macro mensuales (`periodo` y una columna por serie); su JSON describe unidades y fuentes |
| `analitico*.csv` + `.meta.json` | Panel en pesos constantes con derivados (`mix_*`, `cuota_*`, `*_ia`, `spread`, `costo_riesgo`, `eficiencia`, etc.); el `.meta.json` dice la base de los pesos constantes y define cada columna nueva |
| `<análisis>.json` | La salida JSON de cada comando de `analizar.py` (cuotas, brechas, rentabilidad, correlación, segmentar, sensibilidad, anomalías, calidad) |
| `<análisis>.csv` y `.png` | El detalle y el gráfico de cada análisis |
| `borrador.md`, `revision.md` | El borrador y el informe del revisor independiente |

Todos los JSON siguen la misma regla: si hubo un problema, la clave `error` y, cuando corresponde, `ayuda`. Los montos van en millones de pesos (constantes si el archivo lo indica).

## Comandos públicos

`scripts/panel.py` (envoltorio de `consultar_panel.py` del oráculo), `scripts/revisor.py` (ubica al revisor), `scripts/filtro_riesgo.py` (usa riesgo-bancario), `scripts/macro_ar.py` y `scripts/analizar.py` con sus subcomandos: `proforma`, `preparar`, `calidad`, `cuotas`, `brechas`, `rentabilidad`, `correlacion`, `segmentar`, `sensibilidad`, `anomalias`, `novedades` y `grafico`. La ayuda de cada uno sale con `--help`.
