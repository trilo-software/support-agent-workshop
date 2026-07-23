# Los ejercicios

Regla del juego: el repo recién forkeado **deploya verde y el chat responde,
pero responde mal**. Cada ejercicio arregla una pieza, y el cambio se ve en tu
servicio desplegado (edita → commit → push → Render redeploya).

Tu progreso, en cualquier momento:

```bash
uv run pytest -m ejercicio
```

Las pistas van en escalera: intenta con la 1 antes de leer la 2.

---

## Ejercicio 1 — Dale identidad al agente (~10 min)

**Archivo:** `src/support_agent/prompts.py`
**Objetivo:** que el agente sepa quién es, use el contexto, cite fuentes y
sepa cuándo rendirse.

El `SYSTEM_PROMPT` actual es `"Eres un asistente."` — con eso el modelo no
tiene identidad, ignora el bloque `CONTEXTO` que el agente le inyecta (mira
`agent.py`), no cita fuentes y nunca escala. Reescríbelo para que el agente:

1. Se presente como agente de soporte de **Café Pura Vida**, en español.
2. Responda **SOLO** con información del bloque `CONTEXTO`.
3. Cite la fuente entre corchetes, p. ej. `[Envíos]`.
4. Si el contexto no alcanza, lo admita y ofrezca **escalar a un humano**.

**Verifica:**

```bash
uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_1_prompt.py
```

Y en la UI (tras el push): pregunta algo fuera de la KB («¿venden té?») y
mira si lo admite en vez de inventar.

<details><summary>Pista 1</summary>
Mira cómo <code>agent.py</code> arma el mensaje de sistema:
<code>SYSTEM_PROMPT + "\n\nCONTEXTO:\n" + chunks</code>. Tu prompt debe
referirse a ese bloque CONTEXTO por su nombre.
</details>

<details><summary>Pista 2</summary>
Estructura que funciona bien: un párrafo de identidad («Eres el agente de
soporte de Café Pura Vida…») + una lista numerada de reglas (solo CONTEXTO,
citar fuente entre corchetes, admitir cuando no sabe y ofrecer escalar, ser
breve).
</details>

---

## Ejercicio 2 — Enciende el RAG (~15 min)

**Archivo:** `src/support_agent/rag.py`
**Objetivo:** que el retrieval devuelva chunks, y los MÁS parecidos primero.

Dos roturas en el mismo archivo:

- **(a)** `TOP_K = 0`: el agente no recupera ningún chunk. Sube el valor
  (4 funciona bien).
- **(b)** `RETRIEVE_SQL` no tiene `ORDER BY`: la base devuelve chunks en un
  orden arbitrario, no los más parecidos. pgvector te da el operador `<=>`
  (distancia coseno: **menor = más parecido**). El backend en memoria imita
  esta query, así que el mismo fix arregla local y producción.

**Verifica:**

```bash
uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_2_rag.py
```

El momento del workshop: pregunta «¿cuánto tarda el envío a Cartago?» en tu
UI **antes** del push (sin fuentes) y **después** (chips 📚 con fuentes y
scores). También puedes mirar el retrieval crudo:
`https://<tu-servicio>.onrender.com/api/debug/search?q=envío+a+Cartago`

<details><summary>Pista 1 (parte b)</summary>
La cláusula va entre el <code>FROM … JOIN …</code> y el <code>LIMIT</code>.
</details>

<details><summary>Pista 2 (parte b)</summary>
<code>ORDER BY c.embedding &lt;=&gt; $1::vector</code> — ascendente, porque
<code>&lt;=&gt;</code> es distancia (menor = mejor), y el score
<code>1 - distancia</code> ya lo calcula el SELECT.
</details>

---

## Ejercicio 3 — Alimenta la base de conocimiento (~10 min)

**Archivo:** `kb/promociones.md` (¡no existe todavía!)
**Objetivo:** ver que «la KB es solo markdown en git»: agregar conocimiento
es agregar un archivo.

Crea `kb/promociones.md` con la política de promociones de Café Pura Vida.
Invéntala, pero con datos concretos. Contenido mínimo sugerido:

- Un H1: `# Promociones`.
- Un **descuento de primera compra** (porcentaje, código, condiciones).
- Un **programa de referidos** con montos concretos (p. ej. ₡3.000 para cada
  lado).

Push → Render redeploya → la ingesta idempotente detecta el archivo nuevo y
solo embebe ese (míralo en los logs: `ingesta: 6 documentos, 1 nuevos…`).

**Verifica:**

```bash
uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_3_kb.py
```

Y en la UI: «¿tienen descuento para primera compra?» → debería citar
`[Promociones]`.

<details><summary>Pista 1</summary>
Mira cualquier otro archivo de <code>kb/</code> como plantilla: H1 con el
título, secciones <code>##</code>, datos específicos.
</details>

<details><summary>Pista 2</summary>
Si el retrieval no lo encuentra, usa las palabras que la gente preguntaría
(«descuento», «primera compra», «referidos») en el texto del documento. Y
si tu servicio ya estaba desplegado, fuerza la ingesta:
<code>curl -X POST https://&lt;tu-servicio&gt;.onrender.com/api/ingest</code>
</details>

---

## Ejercicio 4 — Mide tu RAG con mini-evals (~25 min)

**Archivos:** `src/support_agent/evals.py`, `evals/preguntas.yaml`
**Objetivo:** interiorizar que un RAG no se mejora «a ojo»: sin evals no
sabes si tu cambio ayudó o empeoró.

Aquí no hay código roto: es un ejercicio de **experimentación**. El runner
toma ~11 preguntas doradas (`evals/preguntas.yaml`) y mide si el documento
esperado aparece en el top-k (*hit*) y si aparece de primero (*hit@1*).

1. **Línea base:**

   ```bash
   uv run python -m support_agent.evals
   ```

2. **Experimento A — top-k:**

   ```bash
   uv run python -m support_agent.evals --top-k 1
   uv run python -m support_agent.evals --top-k 8
   ```

   ¿Cómo cambian *hits* y *hit@1*? ¿Qué costo tiene subir k? (más tokens de
   contexto, más ruido para el modelo — mira el tamaño del bloque CONTEXTO).

3. **Experimento B — chunking:** en `rag.py`, cambia `CHUNK_SIZE` (800 → 200,
   luego → 3000) y `CHUNK_OVERLAP`. Para re-ingestar con el chunking nuevo en
   local basta reiniciar el server (la base en memoria arranca vacía); en
   Render, push + `POST /api/ingest` tras tocar cualquier doc. Usa
   `GET /api/debug/search?q=...` para VER los chunks que regresan con cada
   configuración. **Al final regresa a 800/100.**

4. Pregunta de cierre: ¿qué combinación dio el mejor score y por qué crees?

Este ejercicio no tiene test rojo→verde: su verificación es el score y la
discusión.

---

## Ejercicio 5 — Expón tu RAG por MCP (~30 min)

**Archivo:** `src/support_agent/mcp_server.py`
**Objetivo:** que cualquier cliente MCP use TU retrieval.

Tu servicio ya monta un servidor MCP en `/mcp` con dos tools funcionando
(`check_order_status`, `escalate_to_human`). El tercero — `buscar_kb`, la
joya — devuelve `[]`. Complétalo:

1. Recupera los chunks: `chunks = await retrieve(pregunta, top_k)` — es el
   MISMO `retrieve()` que encendiste en el Ejercicio 2 (y ya embebe la
   pregunta por ti).
2. Devuélvelos como lista de dicts: `titulo`, `fuente`, `score`, `contenido`.

Fíjate cómo `check_order_status` envuelve su handler: es el mismo patrón.

**Verifica:**

```bash
uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_5_mcp.py
```

**Segunda mitad — conecta un cliente MCP real** a tu servicio desplegado
(las tres rutas, con comandos, están en el
[README](../README.md#conecta-tu-servicio-por-mcp)): MCP Inspector,
Claude Code o Claude Desktop.

El aha: el mismo `retrieve()` que arreglaste en el Ejercicio 2 ahora lo
consume Claude **sin que escribieras un solo endpoint específico para él**.
Eso es lo que estandariza MCP.

<details><summary>Pista 1</summary>
La solución cabe en 4 líneas: un <code>await retrieve(...)</code> y un list
comprehension que convierte cada <code>RetrievedChunk</code> en dict.
</details>

<details><summary>Pista 2</summary>
Cada chunk tiene <code>c.title</code>, <code>c.source</code>,
<code>c.score</code> y <code>c.content</code>. Redondea el score
(<code>round(c.score, 3)</code>) para que sea legible.
</details>

<details><summary>Pista 3 (conexión)</summary>
Si Claude Code no conecta, valida primero con el Inspector. Si el redeploy
de Render va lento, conéctate al server local:
<code>http://localhost:3000/mcp</code> también funciona.
</details>

---

## Bonus — Registra el tool de pedidos (~5 min)

**Archivo:** `src/support_agent/tools/__init__.py`
**Objetivo:** ver que un tool son tres cosas (nombre + schema + handler) y un
registro.

`check_order_status` ya está implementado (míralo en
`check_order_status.py`) pero nadie lo registró en `TOOLS`, así que el agente
no puede consultar pedidos. Agrégalo al registry.

**Verifica:**

```bash
uv run pytest -m ejercicio tests/ejercicios/test_bonus_tool.py
```

Y en la UI: «¿cómo va mi pedido CR-1003?» → badge 🔧 `check_order_status` y
el estado real del pedido.

<details><summary>Pista</summary>
Una línea, idéntica a la de <code>escalate_to_human</code> que está justo
arriba.
</details>
