# Revisor: segunda mirada antes de entregar

Este documento es para el **revisor**: un agente que no hizo el análisis y lo lee con ojos frescos antes de que llegue al usuario. Si tu entorno no permite lanzar otro agente, hacé la revisión vos mismo con esta misma lista, releyendo el borrador como si lo hubiera escrito otro.

## Índice
1. Cómo lanzar al revisor (para el analista)
2. Qué recibe el revisor
3. Qué revisa
4. Formato del informe
5. Qué hace el analista con el informe

---

## 1. Cómo lanzar al revisor (para el analista)

Con el borrador terminado y guardado en `trabajo/borrador.md` (junto con los JSON de cada comando y los gráficos en `trabajo/`), lanzá un agente con la herramienta para crear agentes (Agent o Task). Este es el pedido, adaptado:

> Sos el revisor del skill estratega-bancario. Leé `<ruta del skill>/references/revisor.md` (secciones 2 a 4) y revisá el borrador `<ruta>/trabajo/borrador.md`. La pregunta del usuario fue: "<pregunta>". Los datos y salidas del análisis están en `<ruta>/trabajo/`. Recalculá vos los números clave con los CSV (Python con pandas: `<ruta del python si no es el del sistema>`). No modifiques el borrador. Escribí tu informe en `trabajo/revision.md` con el formato de la sección 4 y respondé con el veredicto y la cantidad de hallazgos por gravedad.

Mientras el revisor trabaja, no sigas editando el borrador: esperá su informe.

Pedido para la segunda ronda corta (solo si hubo críticos):

> Sos el revisor del skill estratega-bancario, segunda ronda. Compará `<ruta>/trabajo/borrador_v1.md` con `<ruta>/trabajo/borrador.md` y revisá **solo los cambios**: recalculá los números nuevos o modificados con los CSV de `trabajo/` y confirmá que cada hallazgo crítico de `trabajo/revision.md` quedó resuelto sin introducir errores nuevos. Agregá al final de `trabajo/revision.md` una sección "## Segunda ronda" con veredicto y hallazgos, y respondé con el veredicto.

## 2. Qué recibe el revisor

- La pregunta del usuario.
- `trabajo/borrador.md`: la respuesta propuesta.
- `trabajo/`: los paneles (`panel*.csv`, `analitico*.csv`, `macro.csv`), los JSON y CSV de cada análisis y los gráficos.

## 3. Qué revisa

Revisá en este orden. Para cada hallazgo, buscá la evidencia en los archivos: no opines sin mirar los datos.

**A. Números**
- Elegí los 8 a 12 números que más pesan: el titular, el número central de cada insight y el tamaño de cada oportunidad. Recalculá cada uno desde los CSV (la fila y la columna correctas, no un valor parecido) y anotalos en la tabla de verificación del informe. Un número que no podés reconstruir es un hallazgo crítico.
- Los cálculos derivados (cocientes, sumas, variaciones) dan lo que dice el texto. Un ratio activo / patrimonio, una suma de componentes o un "x veces" mal hecho le hacen perder credibilidad a todo el informe.
- Un mismo dato aparece igual en el texto, las tablas y los gráficos. No se mezclan promedios de varios meses con meses puntuales sin aclararlo.
- Unidades y escalas: millones, miles de millones o billones; % o puntos porcentuales; pesos corrientes o constantes (y de qué mes).

**B. Rigor** (las reglas de rigor de SKILL.md y `metodologia.md`)
- Los montos en el tiempo están en pesos constantes.
- Las fusiones del período están en pro forma, o la respuesta explica por qué no hace falta.
- Si el período cruza una devaluación, el blanqueo o el alivio COVID, lo aclara.
- "El segmento X rinde más" vale con mediana **y** con ponderado, o la diferencia se dice.
- Lo que se llama tendencia, fuga o boom no es un escalón único.
- La fuerza de la evidencia está calificada (robusta, indicio o no concluyente), no hay "causa" con evidencia de correlación y los rezagos que dependen de la especificación se informan como rango.
- No hay datos de memoria: lo que no sale de los archivos está marcado como contexto, con su fuente.

**C. Negocio**
- La respuesta contesta la pregunta que hizo el usuario, en el orden que le importa.
- Cada oportunidad tiene tamaño en stock y en resultado anual, con supuestos y escenarios, sin doble conteo.
- La base de cada tamaño es la correcta: misma moneda que la tasa aplicada (los saldos del balance mezclan pesos y dólares), sin costos únicos tomados como estructurales, y dentro de los límites que la propia respuesta recomienda (topes de crecimiento, apetito de riesgo).
- Las oportunidades que suman riesgo (por ejemplo, crecer donde la mora sube) lo dicen.
- Falta algo obvio que un comité preguntaría. Por ejemplo, un hallazgo que el propio `trabajo/` muestra y la respuesta omite, o una explicación alternativa no descartada.

**D. Gráficos**
- Los PNG citados existen, se ven bien (sin textos encimados ni ejes engañosos) y cada uno dice qué mirar.

## 4. Formato del informe (`trabajo/revision.md`)

```markdown
# Revisión
Veredicto: APROBAR | CORREGIR

## Verificación de números clave
| Número en el borrador | Dónde | Recalculado | Archivo y cálculo | ¿OK? |
|---|---|---|---|---|

## Críticos (cambian una conclusión o un número del titular)
1. [Dónde: sección o frase] Problema. Evidencia: archivo, columna y valor recalculado. Corrección propuesta.

## Importantes (error real, pero no cambia la conclusión)
1. ...

## Menores (forma, claridad)
1. ...

## Lo que está bien (máximo 3 líneas)
```

Veredicto CORREGIR si hay al menos un crítico. Sé concreto y breve: el analista tiene que poder aplicar cada corrección sin adivinar.

## 5. Qué hace el analista con el informe

- **Críticos:** corregir siempre. Si cambia un titular, volvé a correr el análisis que lo sostiene. Si no estás de acuerdo con el revisor, verificalo con los datos: el que tenga la evidencia gana.
- **Importantes:** corregir salvo que no aplique, y en ese caso dejar anotado por qué.
- **Menores:** corregir si es rápido.
- **Si hubo críticos, una segunda ronda corta, solo sobre los cambios.** Las correcciones grandes introducen errores nuevos. En las pruebas, una corrección contó dos veces un cargo extraordinario y otra sobredimensionó una oportunidad. Antes de editar, guardá el borrador original como `trabajo/borrador_v1.md`. Después pedile al revisor (otro agente) que mire **solo** lo que cambió entre `borrador_v1.md` y `borrador.md`: que recalcule los números nuevos y confirme que cada crítico quedó resuelto. No repite la revisión completa. Si no hubo críticos, no hace falta segunda ronda.
- **No más de dos rondas.** Una revisión completa de nuevo casi duplica el tiempo y en las pruebas solo agregó correcciones menores.
- En "Fuentes y método" de la respuesta final, una línea: "Revisado por un segundo analista: N correcciones aplicadas (C críticas)".
