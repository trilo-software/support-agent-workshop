# Workshop: Agente de Soporte con RAG y MCP en Render

Vas a construir, medir y exponer un **agente de soporte al cliente** para
**Café Pura Vida**, una tienda ficticia de café de especialidad costarricense.
El agente responde usando **RAG** (Retrieval-Augmented Generation) sobre una
base de conocimiento en **Postgres + pgvector**, con **Gemini** como modelo, y
al final expone su retrieval como **servidor MCP** para que Claude (o
cualquier cliente MCP) lo consuma.

El repo llega **deliberadamente incompleto**: deploya y responde, pero
responde mal. Tu trabajo son 5 ejercicios (+1 bonus) que lo arreglan pieza
por pieza — y cada arreglo se ve en vivo en tu servicio desplegado.

```
                     ┌──────────────────────────────────────────┐
  Navegador ────────▶│  Web Service (FastAPI) — «naive agent»   │
  (chat UI)  POST    │                                          │
             /api/…  │  1. embed(pregunta)     ──▶ Gemini embed │
                     │  2. retrieve(top_k)     ──▶ pgvector     │
  Claude Code /      │  3. loop agente + tools ──▶ Gemini chat  │
  MCP Inspector ────▶│  4. respuesta + fuentes citadas          │
  (cliente MCP) /mcp │                                          │
                     │  /mcp → servidor MCP: buscar_kb, pedidos │
                     └───────────────────┬──────────────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │   Render Postgres   │
                              │  pgvector · orders  │
                              └─────────────────────┘

  Ingesta (al arrancar, idempotente): kb/*.md → chunks → embeddings
```

**Las dos ideas del workshop:** (a) un agente con RAG no es magia — es trocear
documentos, guardar embeddings, buscar por similitud e inyectar el resultado
en el prompt; y no se mejora «a ojo» sino midiendo con evals. (b) MCP tampoco
es magia — es el protocolo estándar para que cualquier cliente consuma las
capacidades que TÚ construiste, sin escribir un endpoint específico para cada
uno.

## Requisitos

- Cuenta en la organización de Render del facilitador (te llegó una invitación).
- Token de Gemini (te lo da el facilitador).
- Cuenta de GitHub.
- Para correr en local (opcional pero recomendado): Python ≥ 3.12, [`uv`](https://docs.astral.sh/uv/) y git.

## Paso 0 — Fork + Action `setup-attendee`

1. Haz **fork** de este repo a tu cuenta de GitHub.
2. En tu fork: pestaña **Actions** → habilita los workflows → elige
   **setup-attendee** → **Run workflow**.

La Action prefija los recursos del `render.yaml` con tu usuario de GitHub
(`tu-usuario-support-agent`, etc.) para que no colisionen con los del resto
de asistentes en la organización compartida de Render.

## Paso 1 — Deploy del Blueprint en Render

1. En el [dashboard de Render](https://dashboard.render.com): **New +** →
   **Blueprint** → conecta tu fork.
2. Render lee el `render.yaml` y propone un web service + una base Postgres.
3. Te pedirá el valor de **`GEMINI_API_KEY`**: pega el token que te dio el
   facilitador. *(Alternativa: el facilitador puede tener un env group
   compartido — pregunta.)*
4. **Apply** y espera el primer deploy (~3–5 min). El servicio queda en una
   URL tipo `https://tu-usuario-support-agent.onrender.com`.

Con `autoDeploy: true`, cada `git push` a tu fork redeploya solo. Ese es el
ciclo de todos los ejercicios: **edita → commit → push → mira el cambio en
tu URL**.

## Paso 2 — Pruébalo (y mira cómo responde de mal)

Abre tu URL y pregunta en el chat:

> ¿Cuánto tarda el envío a Cartago?

La respuesta es genérica, sin fuentes, o directamente inventada. No está
roto el deploy: está roto el agente, a propósito. Los ejercicios lo arreglan.

## Los ejercicios

El detalle completo (con pistas escalonadas) está en
[workshop/ejercicios.md](workshop/ejercicios.md). Tu progreso se mide con:

```bash
uv run pytest -m ejercicio   # rojos al inicio → verdes al completar
```

| # | Qué arreglas | Archivo | Tiempo |
| --- | --- | --- | --- |
| 1 | El system prompt: identidad, contexto, citas, escalamiento | `src/support_agent/prompts.py` | ~10 min |
| 2 | Encender el RAG: `TOP_K` y el `ORDER BY` de la query | `src/support_agent/rag.py` | ~15 min |
| 3 | Alimentar la KB: crea `kb/promociones.md` | `kb/` | ~10 min |
| 4 | Medir con mini-evals: experimentos de top-k y chunking | `src/support_agent/evals.py` | ~25 min |
| 5 | Exponer tu RAG por MCP: completa `buscar_kb` | `src/support_agent/mcp_server.py` | ~30 min |
| ★ | Bonus: registra el tool de pedidos | `src/support_agent/tools/__init__.py` | ~5 min |

## Conecta tu servicio por MCP

Tu servicio expone un servidor MCP en `/mcp` (transporte HTTP streamable).
Tres formas de conectarte (con el Ejercicio 5 resuelto):

**1. MCP Inspector** (sin cuenta, siempre funciona):

```bash
npx @modelcontextprotocol/inspector
```

Conecta a `https://<tu-servicio>.onrender.com/mcp` (transporte *Streamable
HTTP*), lista los tools e invoca `buscar_kb` a mano.

**2. Claude Code** (el wow):

```bash
claude mcp add --transport http cafe-pura-vida https://<tu-servicio>.onrender.com/mcp
```

Y pregúntale a Claude: *«¿cuánto tarda un envío de Café Pura Vida a
Cartago?»* — Claude llamará a `buscar_kb` de TU servicio y responderá con TU
base de conocimiento.

**3. Claude Desktop**: Settings → Connectors → Add custom connector, con la
URL `https://<tu-servicio>.onrender.com/mcp` (requiere un plan que soporte
conectores remotos).

> ⚠ El endpoint `/mcp` va **sin autenticación** en este workshop: es de solo
> lectura sobre datos ficticios. En producción se protegería con OAuth o un
> token (el SDK de MCP soporta ambos).

## Correr en local

```bash
uv sync                                # instala dependencias
uv run pytest                          # suite normal (verde desde el inicio)
uv run pytest -m ejercicio             # tu progreso en los ejercicios
uv run python -m support_agent.server  # http://localhost:3000
uv run python -m support_agent.evals   # mini-evals de retrieval
```

Sin `GEMINI_API_KEY` ni `DATABASE_URL`, todo corre en **modo mock**
determinista con la base **en memoria**: sin credenciales, sin Postgres, sin
red. Las respuestas empiezan con `[mock]`, pero el RAG, los tools, los evals
y el MCP funcionan de verdad — ideal para desarrollar.

## Variables de entorno

| Var | Requerida | Notas |
| --- | --- | --- |
| `GEMINI_API_KEY` | En Render sí | Sin ella, modo mock determinista (local y tests) |
| `AGENT_MODEL` | No | `mock` fuerza el mock aunque haya key |
| `GEMINI_MODEL` | No | Default `gemini-2.5-flash` |
| `GEMINI_EMBED_MODEL` | No | Default `gemini-embedding-001` (768 dims) |
| `DATABASE_URL` | En Render la inyecta el Blueprint | Sin ella, backend en memoria |
| `PORT` | No | Default `3000` |

## Variante free tier

El Blueprint funciona con planes gratuitos, con restricciones:

- **Solo una Postgres free por workspace**: en la organización compartida solo
  el primero podría crearla. La variante free funciona si **cada quien usa su
  workspace personal gratuito** de Render (ahí `setup-attendee` ya no es
  necesario, aunque no estorba).
- La Postgres free **expira a los 30 días**; el web service free **se duerme
  tras 15 min** sin tráfico (el primer request tarda ~1 min en despertarlo).
- **Sin base de datos también funciona**: borra el bloque `databases:` y el
  envVar `DATABASE_URL` del `render.yaml` y cambia los planes a `free`. El
  RAG vive en memoria (la ingesta corre al arrancar); pierdes persistencia de
  tickets entre reinicios — aceptable para el workshop.

## Troubleshooting

| Síntoma | Fix |
| --- | --- |
| El deploy falla en build | Mira los logs: casi siempre es no haber corrido la Action `setup-attendee` (colisión de nombres) o un `render.yaml` editado a mano |
| Gemini devuelve 429 (rate limit) | Agrega `AGENT_MODEL=mock` como env var del servicio en Render: todo sigue funcionando en modo mock |
| El chat responde sin fuentes | Es el estado inicial: Ejercicios 1 y 2 |
| «La ingesta no corrió» / no encuentra un doc nuevo | La ingesta corre al arrancar; fuerza con `curl -X POST https://<tu-servicio>.onrender.com/api/ingest` |
| El cliente MCP no conecta | Prueba primero con el Inspector; verifica que la URL termina en `/mcp`; en free tier el primer request despierta al servicio — reintenta |
| Nombres colisionan en Render | Corre la Action `setup-attendee` en tu fork y vuelve a crear el Blueprint |

## Siguiente paso

Este agente usa el patrón **naive**: todo pasa dentro del request HTTP (mira
el docstring de `src/support_agent/server.py` para saber por qué eso no
escala). Caminos para seguir:

- Sacar el trabajo del request: colas + workers, o **Render Workflows**.
- **Retrieval as a tool**: que el modelo decida cuándo buscar en la KB, en
  vez de recuperar siempre.
- **Auth para el servidor MCP** (OAuth/token).
- Más evals: medir también la calidad de la *respuesta* (no solo el
  retrieval), p. ej. con un LLM como juez.
