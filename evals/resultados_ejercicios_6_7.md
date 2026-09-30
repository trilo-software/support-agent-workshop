# Resultados de los ejercicios 6 y 7

## Ejercicio 6: evaluar la recuperación

Las mediciones usan embeddings mock y una base en memoria. Antes de cada
configuración se vació la base y se volvió a ingerir la documentación para
aplicar el nuevo tamaño de fragmentos. Los resultados no miden la calidad de
las respuestas de Gemini.

La línea base con las 11 preguntas originales, top-k 4 y fragmentos 800/100
encontró 11/11 fuentes esperadas y colocó 10/11 en primer lugar.

Se agregaron dos preguntas a `preguntas.yaml`:

- ¿Cuándo vence el crédito del programa de referidos? → `kb/promociones.md`.
- ¿Qué molienda recomiendan para prensa francesa? → `kb/productos.md`.

### Comparación con las 13 preguntas

| Tamaño / solapamiento | top-k | Fuentes encontradas | En primer lugar | Fragmentos indexados | Caracteres recuperados, promedio |
| --- | --- | --- | --- | --- | --- |
| 800 / 100 | 4 | 13/13 | 12/13 | 35 | 2004 |
| 800 / 100 | 1 | 12/13 | 12/13 | 35 | 516 |
| 800 / 100 | 8 | 13/13 | 12/13 | 35 | 3969 |
| 200 / 40 | 4 | 13/13 | 12/13 | 112 | 653 |
| 3000 / 300 | 4 | 13/13 | 12/13 | 32 | 2045 |

Los caracteres cuentan el contenido de los fragmentos, sin las etiquetas
que el agente añade al bloque CONTEXTO. No son una medición de tokens.

Las dos preguntas nuevas encuentran su fuente en primer lugar con la
configuración predeterminada. La pregunta sobre devolver una bolsa sin abrir
queda en tercer lugar; por eso top-k 1 falla en ese caso. Subir top-k no
cambia el primer resultado: solo incluye más resultados de la misma lista.

### Conclusión

Las configuraciones con top-k 4 y 8 empatan en estas métricas. La de 200/40
recupera menos texto con el mismo acierto, pero genera más fragmentos y puede
separar condiciones importantes. Encontrar el documento correcto no garantiza
que el fragmento contenga toda la respuesta. Conviene evaluar también las
respuestas antes de elegir esa configuración.

Top-k 8 casi duplica el texto frente a top-k 4 sin mejorar los aciertos de
este conjunto. Los fragmentos de 3000 tampoco aportan una mejora; el algoritmo
separa por secciones antes de aplicar el tamaño, así que no todas llegan a
3000 caracteres.

Se conservan los valores pedidos al finalizar: `CHUNK_SIZE = 800`,
`CHUNK_OVERLAP = 100` y `TOP_K = 4`. Los valores experimentales se aplicaron
solo en el proceso de evaluación, sin modificar `rag.py` en disco.

`resultados_ejercicio_6.json` contiene los resultados por pregunta y ejemplos
completos de `GET /api/debug/search` para cada configuración. Las solicitudes
se ejecutaron contra la aplicación local mediante el transporte ASGI de httpx.

Para repetir las evaluaciones estándar en modo mock con el mismo entorno,
establece `AGENT_MODEL=mock`, `DATABASE_URL` vacío y `GEMINI_API_KEY` vacío
antes de importar la aplicación; luego ejecuta:

```bash
uv run python -X utf8 -m support_agent.evals
uv run python -X utf8 -m support_agent.evals --top-k 1
uv run python -X utf8 -m support_agent.evals --top-k 8
```

Para repetir el experimento de fragmentos, cambia temporalmente el tamaño y
solapamiento a 200/40 y luego a 3000/300, ejecutando cada evaluación en un
proceso nuevo con la base en memoria. Al terminar, restaura 800/100.

## Ejercicio 7: publicar la búsqueda por MCP

`buscar_kb` ahora llama a `retrieve(pregunta, top_k)` y devuelve `titulo`,
`fuente`, `score` redondeado a tres decimales y `contenido` por fragmento.
La descripción incluye las promociones disponibles en la base.

Se verificó localmente:

- La sesión MCP puede listar y llamar a `buscar_kb`.
- El endpoint `/mcp`, probado con TestClient de FastAPI, acepta la
  inicialización, lista las tres herramientas y responde a sus llamadas.
- Una consulta de envíos con top-k 2 devuelve dos fragmentos, primero de
  `kb/envios.md`, con los cuatro campos esperados.
- `check_order_status` devuelve `en_transito` para `CR-1003`.
- Pasan las 25 pruebas de los ejercicios y las 3 pruebas de integración
  del evaluador y del listado de herramientas MCP.

### Validación remota pendiente

Falta desplegar estos cambios y disponer de la URL pública del servicio para
comprobarlo con MCP Inspector y con Gemini. Las pruebas locales usan mock y
TestClient; no verifican un despliegue de Render ni una llamada real de Gemini.
Con el servicio actualizado y una clave de Gemini configurada, ejecutar:

```bash
npx @modelcontextprotocol/inspector
uv run python scripts/preguntar_por_mcp.py https://<tu-servicio>.onrender.com/mcp "¿cuánto tarda el envío a Cartago?"
uv run python scripts/preguntar_por_mcp.py https://<tu-servicio>.onrender.com/mcp "¿cómo va el pedido CR-1003?"
```

En el Inspector, seleccionar Streamable HTTP, conectar a la misma URL, listar
las herramientas y llamar a `buscar_kb`.
