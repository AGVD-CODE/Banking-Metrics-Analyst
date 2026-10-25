# Cómo se probó el skill

## Método

Se usaron tres preguntas realistas, como las haría un usuario:

1. **Macro frente a los grandes:** *"Trabajo en planeamiento estratégico de Banco Macro. El directorio nos pide entender en qué productos estamos perdiendo terreno frente a los grandes privados (Galicia, Santander, BBVA) en los últimos dos años y qué oportunidades concretas de negocio tenemos para el plan 2027."*
2. **Mora de consumo y macro:** *"¿Qué variables de la macro anticipan la mora de consumo en los bancos argentinos y con cuántos meses de rezago? ¿Qué bancos son más sensibles? ¿Hay espacio para que un banco con mora más baja gane cuota en préstamos personales mientras los demás frenan?"*
3. **Segmentación y Supervielle:** *"Segmentá a los bancos argentinos por modelo de negocio y decime qué modelos son los más rentables. Soy consultor y estoy preparando una propuesta para Supervielle: ¿qué hay escondido en los datos que ellos podrían aprovechar?"*

Cada pregunta se respondió en tres configuraciones:
- con la versión actual del skill (con revisor independiente);
- con la versión anterior (sin revisor);
- sin el skill. En este caso, el agente tenía acceso a los mismos datos a través de BCRA-Oracle y tuvo que programar todo por su cuenta.

Un corrector independiente (otro agente) calificó cada respuesta con 10 a 12 criterios verificables. Para hacerlo recalculó desde los archivos de datos al menos tres números clave por respuesta.

## Criterios

Comunes a las tres preguntas:
- cita al BCRA y el período de los datos;
- compara montos en pesos constantes;
- incluye al menos 2 gráficos;
- presenta al menos 2 oportunidades con tamaño;
- explicita límites y riesgos;
- **los números son consistentes** entre texto, tablas y gráficos;
- al menos una oportunidad tiene **resultado anual estimado** con supuestos.

Específicos:
- **Macro:** cambio de cuota en al menos 3 productos, comparación con los tres competidores e identificación de dónde pierde.
- **Mora:** variables con rezago, evidencia estadística calificada, ranking de sensibilidad de los bancos y oportunidad contracíclica con tamaño y advertencia de riesgo.
- **Supervielle:**
  - al menos 3 segmentos con sus bancos;
  - rentabilidad por segmento;
  - ubicación de Supervielle y sus pares;
  - oportunidades específicas con tamaño;
  - **el "segmento más rentable" vale con la mediana y con el promedio ponderado.**

## Resultados

| Pregunta | Skill actual | Versión anterior | Sin skill |
|---|---|---|---|
| Macro frente a los grandes | 10/10 | 10/10 | 9/10 |
| Mora de consumo y macro | 11/11 | 11/11 | 8/11 |
| Segmentación y Supervielle | 12/12 | 10/12 | 12/12 |
| **Total** | **33/33** | **31/33** | **29/33** |

En las tres preguntas, el corrector eligió la respuesta del skill actual como la más sólida para un comité:

- **Macro:** corrigió los dos problemas de la versión anterior. Una oportunidad de fondeo estaba valuada con tasas en pesos sobre saldos que en un 55 % eran en dólares. Y un salto de un solo mes (marzo de 2025) se había leído como ganancia de cuota. La respuesta sin el skill tenía un error de cálculo (apalancamiento de 2,9 veces cuando era 3,9).
- **Mora:** validó fuera de muestra el ranking de sensibilidad de los bancos y mostró que la mora baja de Nación está "diluida" por su propio crecimiento. La respuesta sin el skill dimensionó una sola oportunidad y afirmó causalidad sin matices.
- **Supervielle:** corrigió un titular de la versión anterior que se apoyaba solo en medianas, cuando el promedio ponderado del mismo segmento contaba otra historia.

## El aporte del revisor independiente

En cada análisis el revisor encontró **2 errores críticos** antes de que la respuesta llegara al usuario, además de errores importantes y menores (entre 15 y 19 correcciones por análisis). Por ejemplo:
- un titular que ocultaba un salto de un mes en la serie;
- una oportunidad valuada sobre una base que mezclaba pesos y dólares;
- rangos de rezago que salían de una sola especificación del modelo.

Una segunda mirada sobre las correcciones detectó un error **introducido por una de ellas**: un cargo por indemnizaciones contado dos veces. Por eso, cuando hay críticos, el skill hace una segunda revisión corta, solo sobre lo que cambió.

## Costo

Cada análisis completo llevó entre 20 y 45 minutos y del orden de 300 a 400 mil tokens. La revisión agrega tiempo, pero es la que garantiza que los números que llegan a un comité estén verificados.

## Cómo repetir las pruebas

Los casos están en [`skill/estratega-bancario/evals/`](../skill/estratega-bancario/evals/), en el formato de `claude plugin eval`. Desde la carpeta del skill, con Claude Code:

```bash
cd skill/estratega-bancario
claude plugin eval . --allow-tools Write,Edit,Bash,Agent
```

Son corridas reales y facturadas: cada caso tarda entre 30 y 45 minutos.
