# Los ejercicios

Regla del juego: tu rama recién creada **deploya verde y el chat responde,
pero responde mal**. Cada ejercicio arregla una pieza, y el cambio se ve en tu
servicio desplegado (edita → commit → push → Render redeploya).

Son siete, en este orden, y todos cuentan:

| #   | Ejercicio                                | Acto                |
| --- | ---------------------------------------- | ------------------- |
| 1   | Dale identidad al agente (system prompt) | 1 · Construir       |
| 2   | Enciende el RAG                          | 1 · Construir       |
| 3   | Alimenta la base de conocimiento         | 1 · Construir       |
| 4   | Registra un tool existente               | 1 · Construir       |
| 5   | Construye tu propio tool                 | 1 · Construir       |
| 6   | Mide tu RAG con mini-evals               | 2 · Medir y exponer |
| 7   | Expón tu RAG por MCP                     | 2 · Medir y exponer |

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
`agent.py`), no cita fuentes y, sin información, escala todo a un humano.
Reescríbelo para que el agente:

1. Se presente como agente de soporte de **Correos de Costa Rica**, en español.
2. Responda **SOLO** con información del bloque `CONTEXTO`.
3. Cite la fuente entre corchetes, p. ej. `[Envíos]`.
4. Si el contexto no alcanza, lo admita y ofrezca **escalar a un humano**.

**Verifica:**

```bash
uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_1_prompt.py
```

Y en la UI (tras el push): pregunta algo fuera de la KB («¿venden té?») y
mira si lo admite en vez de inventar. Todavía sin fuentes: eso viene en el 2.

<details><summary>Pista 1</summary>
Mira cómo <code>agent.py</code> arma el mensaje de sistema:
<code>SYSTEM_PROMPT + "\n\nCONTEXTO:\n" + chunks</code>. Tu prompt debe
referirse a ese bloque CONTEXTO por su nombre.
</details>

<details><summary>Pista 2</summary>
Estructura que funciona bien: un párrafo de identidad («Eres el agente de
soporte de Correos de Costa Rica…») + una lista numerada de reglas (solo CONTEXTO,
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
  (distancia coseno: **menor = más parecido**). El backend en memoria (el que
  corre en el workshop) imita esta query: mientras no tenga `ORDER BY`,
  tampoco ordena. El mismo fix vale para el Postgres real de la variante con
  pgvector.

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

Crea `kb/promociones.md` con la política de promociones de Correos de Costa Rica.
Invéntala, pero con datos concretos. Contenido mínimo sugerido:

- Un H1: `# Promociones`.
- Un **descuento de primera compra** (porcentaje, código, condiciones).
- Un **programa de referidos** con montos concretos (p. ej. ₡3.000 para cada
  lado).

Push → Render redeploya → la ingesta corre al arrancar y ahora ve 6
documentos (míralo en los logs: `ingesta: 6 documentos, 6 nuevos…`; como el
índice vive en memoria, cada arranque embebe todo desde cero).

La ingesta es **idempotente por hash**: si la vuelves a lanzar sin cambiar
nada, no embebe nada. Compruébalo en tu servicio:

```bash
curl -X POST https://<tu-servicio>.onrender.com/api/ingest
# → {"documentos": 6, "ingresados": 0, "chunks_nuevos": 0, ...}
```

Y en local, con el server corriendo, la versión más vistosa: crea el archivo,
lanza `curl -X POST http://localhost:3000/api/ingest` y verás `"ingresados": 1`
sin reiniciar nada.

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
(«descuento», «primera compra», «referidos») en el texto del documento. Si
el archivo está en tu rama pero el servicio no lo ve, revisa en los logs de
Render que el último deploy sea el de tu push.
</details>

---

## Ejercicio 4 — Registra un tool existente (~8 min)

**Archivo:** `src/support_agent/tools/__init__.py`
**Objetivo:** ver que un tool son tres cosas (nombre + schema + handler) y un
registro, y que el agente solo puede usar lo que está registrado.

`check_order_status` ya está implementado (léelo completo en
`check_order_status.py`: descripción, schema JSON de parámetros y handler)
pero nadie lo registró en `TOOLS`, así que el agente no puede consultar
pedidos. Agrégalo al registry.

**Verifica:**

```bash
uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_4_registrar_tool.py
```

Y en la UI: «¿cómo va mi pedido CR-1003?» → badge 🔧 `check_order_status` y
el estado real del pedido. Antes del push, el agente no tenía forma de
saberlo.

<details><summary>Pista</summary>
Una línea, idéntica a la de <code>escalate_to_human</code> que está justo
arriba.
</details>

---

## Ejercicio 5 — Construye tu propio tool (~20 min)

**Archivos:** `src/support_agent/tools/calcular_envio.py` y
`src/support_agent/tools/__init__.py`
**Objetivo:** escribir un tool de cero: la descripción que el modelo lee, el
schema de los argumentos que tiene que extraer, y el handler que hace el
trabajo. Y la regla de oro: **el modelo extrae los argumentos; el precio y
el plazo los calcula el código, nunca el modelo.**

Vas a crear `calcular_envio(canton, monto_pedido)`. Hoy, si un cliente
pregunta «¿cuánto me sale un pedido de ₡12.000 a Turrialba?», el agente lee
`envios.md` y hace la cuenta él mismo: a veces bien, a veces no. Con el tool,
el modelo solo tiene que reconocer el cantón y el monto, y el código responde
con la zona, el costo (con la regla de envío gratis) y los días hábiles.

El archivo `calcular_envio.py` ya trae la tabla de zonas, las tarifas y una
función para normalizar tildes. Te falta:

- **(a)** El `handler`: busca la zona del cantón, aplica la tarifa, decide si
  el envío es gratis (pedidos superiores a ₡25.000) y devuelve un dict con
  `canton`, `zona`, `costo`, `envio_gratis` y `dias_habiles`. Si el cantón
  no está en la tabla, devuelve `{"error": "..."}` explicando qué zonas
  existen: ese texto es lo que el modelo usará para preguntarle al cliente.
- **(b)** El `tool`: una descripción útil (qué hace, cuándo usarlo, qué
  devuelve) y el schema JSON con `canton` (string) y `monto_pedido`
  (integer, colones), ambos requeridos y cada uno con su `description`.
- **(c)** Registrarlo en `TOOLS`, como en el Ejercicio 4.

**Verifica:**

```bash
uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_5_tool_propio.py
```

Y en la UI, tras el push: «¿cuánto me sale un pedido de ₡12.000 a
Turrialba?» → badge 🔧 `calcular_envio` y una respuesta con ₡2.500 y 2 a 3
días hábiles. Prueba también un monto grande («un pedido de ₡40.000 a
Limón») y un cantón que no exista.

<details><summary>Pista 1 (handler)</summary>
<code>ZONAS.get(_normalizar(canton))</code> te da la zona o <code>None</code>.
Con la zona, <code>TARIFAS[zona]</code> trae costo y días. El envío es gratis
si <code>monto_pedido &gt; ENVIO_GRATIS_DESDE</code>.
</details>

<details><summary>Pista 2 (descripción y schema)</summary>
Copia la forma de <code>check_order_status.py</code>. La descripción es un
párrafo para el modelo: «Cotiza el envío… dado el cantón y el monto…
devuelve zona, costo y días hábiles. Úsalo cuando el cliente pregunte cuánto
cuesta o cuánto tarda un envío». Cada parámetro con
<code>"type"</code> y <code>"description"</code>, y ambos en
<code>"required"</code>.
</details>

<details><summary>Pista 3 (¿por qué no lo llama?)</summary>
Si el modelo responde con la cuenta hecha «a mano» en vez de llamar al tool,
casi siempre es la descripción: dile explícitamente cuándo usarlo. Y revisa
que esté en <code>TOOLS</code>: el modelo solo ve lo registrado.
</details>

---

## Ejercicio 6 — Mide tu RAG con mini-evals (~30 min)

**Archivos:** `evals/preguntas.yaml`, `src/support_agent/evals.py`
**Objetivo:** interiorizar que un RAG no se mejora «a ojo»: sin evals no
sabes si tu cambio ayudó o empeoró.

El runner toma las preguntas doradas de `evals/preguntas.yaml` y mide si el
documento esperado aparece en el top-k del retrieval (_hit_) y si aparece de
primero (_hit@1_).

1. **Línea base:**

   ```bash
   uv run python -m support_agent.evals
   ```

2. **Tu entregable: dos preguntas doradas nuevas.** Agrega al final de
   `evals/preguntas.yaml` dos preguntas que un cliente real haría, con su
   `fuente_esperada`. Al menos una debe responderse con tu
   `kb/promociones.md` del Ejercicio 3. Vuelve a correr los evals: ¿las
   encuentra? Si no, ajusta la pregunta (o el documento) hasta que sí.
   Eso es exactamente lo que hace un equipo de verdad con su set dorado.

   ```bash
   uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_6_evals.py
   ```

3. **Experimento A — top-k:**

   ```bash
   uv run python -m support_agent.evals --top-k 1
   uv run python -m support_agent.evals --top-k 8
   ```

   ¿Cómo cambian _hits_ y _hit@1_? ¿Qué costo tiene subir k? (más tokens de
   contexto, más ruido para el modelo — mira el tamaño del bloque CONTEXTO).

4. **Experimento B — chunking:** en `rag.py`, cambia `CHUNK_SIZE` (800 → 200,
   luego → 3000) y `CHUNK_OVERLAP`. Para re-ingestar con el chunking nuevo
   basta reiniciar: en local, reinicia el server (el índice en memoria
   arranca vacío); en Render, el push redeploya y re-ingesta solo. Usa
   `GET /api/debug/search?q=...` para VER los chunks que regresan con cada
   configuración. **Al final regresa a 800/100.**

5. Pregunta de cierre: ¿qué combinación dio el mejor score y por qué crees?

Los evals corren en tu máquina: sin `GEMINI_API_KEY` en tu `.env` usan los
embeddings mock (los números de referencia de la guía son con mock); con la
key usan Gemini de verdad y los números cambian — compara siempre contra TU
línea base.

<details><summary>Pista (mis preguntas no aparecen)</summary>
Con el mock, el retrieval es por palabras compartidas: usa en la pregunta
palabras que estén en el documento («referidos», «primera compra», «prensa
francesa»). Con Gemini real es semántico y perdona más, pero la lección es la
misma: el set dorado se afina.
</details>

---

## Ejercicio 7 — Expón tu RAG por MCP (~30 min)

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
uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_7_mcp.py
```

**Segunda mitad — que otro agente use tu servidor.** Con el push hecho y tu
servicio despierto:

1. **Valida con el MCP Inspector** (`npx @modelcontextprotocol/inspector`):
   conecta a `https://<tu-servicio>.onrender.com/mcp`, lista los tools y
   llama `buscar_kb` a mano. Si aquí no sale, nada más va a salir.
2. **Deja que Gemini lo use solo.** Con `GEMINI_API_KEY` en tu `.env`:

   ```bash
   uv run python scripts/preguntar_por_mcp.py https://<tu-servicio>.onrender.com/mcp "¿cuánto tarda el envío a Cartago?"
   ```

   El script le pasa a la API de Gemini la URL de TU servidor MCP; Gemini
   decide llamar `buscar_kb`, tu servicio le devuelve los chunks y Gemini
   responde con ellos. Prueba también «¿cómo va el pedido CR-1003?».

3. Opcional: un agente en tu terminal, Gemini CLI (gratis) o Claude Code
   (cuenta de pago). Comandos en el
   [README](../README.md#conecta-tu-servicio-por-mcp).

**Paso extra (opcional): expón también tu `calcular_envio`.** Tres líneas en
`mcp_server.py` con el mismo patrón de `check_order_status`, push, y
pregúntale a Gemini por el script «¿cuánto cuesta enviar un pedido de 12000
a Limón?». Tu tool del Ejercicio 5 ahora lo usa otro agente.

El aha: el mismo `retrieve()` que arreglaste en el Ejercicio 2 (y el tool
que escribiste en el 5) ahora los consume otro agente **sin que escribieras
un solo endpoint específico para él**. Eso es lo que estandariza MCP.

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
Si el script o un agente no conectan, valida primero con el Inspector. Si el
servicio estaba dormido (free tier), ábrelo en el navegador para despertarlo
y reintenta. El script de Gemini necesita la URL pública (no localhost); el
Inspector y Claude Code sí pueden usar <code>http://localhost:3000/mcp</code>
si el redeploy de Render va lento.
</details>
