# Workshop: Agente de Soporte con RAG y MCP en Render

Vas a construir, medir y exponer un **agente de soporte al cliente** para
**Café Pura Vida**, una tienda ficticia de café de especialidad costarricense.
El agente responde usando **RAG** (Retrieval-Augmented Generation) sobre una
base de conocimiento en markdown, con **Gemini** como modelo, y al final
expone su retrieval como **servidor MCP** para que Claude (o cualquier cliente
MCP) lo consuma.

El repo llega **deliberadamente incompleto**: deploya y responde, pero
responde mal. Tu trabajo son 5 ejercicios (+1 bonus) que lo arreglan pieza
por pieza — y cada arreglo se ve en vivo en tu servicio desplegado.

```
                     ┌──────────────────────────────────────────┐
  Navegador ────────▶│  Web Service free (FastAPI) — «naive»    │
  (chat UI)  POST    │                                          │
             /api/…  │  1. embed(pregunta)     ──▶ Gemini embed │
                     │  2. retrieve(top_k)     ──▶ índice en    │
  Claude Code /      │                             memoria      │
  MCP Inspector ────▶│  3. loop agente + tools ──▶ Gemini chat  │
  (cliente MCP) /mcp │  4. respuesta + fuentes citadas          │
                     │                                          │
                     │  /mcp → servidor MCP: buscar_kb, pedidos │
                     └──────────────────────────────────────────┘

  Ingesta (al arrancar, idempotente): kb/*.md → chunks → embeddings → memoria
```

**Las dos ideas del workshop:** (a) un agente con RAG no es magia — es trocear
documentos, guardar embeddings, buscar por similitud e inyectar el resultado
en el prompt; y no se mejora «a ojo» sino midiendo con evals. (b) MCP tampoco
es magia — es el protocolo estándar para que cualquier cliente consuma las
capacidades que TÚ construiste, sin escribir un endpoint específico para cada
uno.

**Sobre la base de datos:** en el workshop el RAG vive **en memoria** dentro
del web service (plan free de Render, sin Postgres). El código para
**Postgres + pgvector** está incluido y se activa con una sola variable
(`DATABASE_URL`): la query SQL que arreglas en el Ejercicio 2 es la que
correría ahí, y el backend en memoria la imita. Cómo encenderlo: ver
[Variante con Postgres + pgvector](#variante-con-postgres--pgvector).

## Requisitos

- Cuenta de GitHub con acceso de escritura a este repo (te llegó una
  invitación como colaborador).
- Cuenta en el workspace de Render del facilitador (te llegó una invitación).
- Key de Gemini: no necesitas una propia, ya está en el workspace (para
  correr en local con Gemini real sí te sirve una en tu `.env`, opcional).
- Para correr en local (opcional pero recomendado): Python ≥ 3.12, [`uv`](https://docs.astral.sh/uv/) y git.
- Para el Ejercicio 5: Node.js ≥ 18 (`npx`) para el MCP Inspector, o Claude Code.

## Paso 0 — Tu rama + Action `setup-attendee`

Cada asistente trabaja en **su propia rama** de este repo, con el nombre de
su usuario de GitHub. `main` está protegida: no hagas push ahí.

1. Clona el repo y crea tu rama:

   ```bash
   git clone https://github.com/trilo-software/support-agent-workshop.git
   cd support-agent-workshop
   git checkout -b tu-usuario
   git push -u origin tu-usuario
   ```

2. En GitHub: pestaña **Actions** → **setup-attendee** → **Run workflow** →
   en «Use workflow from» elige **tu rama** → **Run workflow**.

La Action prefija los recursos del `render.yaml` con tu usuario de GitHub
(`tu-usuario-support-agent`, etc.) para que no colisionen con los del resto
de asistentes en el workspace compartido de Render, y commitea el cambio en
tu rama. Haz `git pull` para traértelo.

*(Sin la Action: `uv run python scripts/setup_attendee.py tu-usuario` en
local, y commit + push.)*

## Paso 1 — Deploy del Blueprint en Render

1. En el [dashboard de Render](https://dashboard.render.com), dentro del
   workspace del facilitador: **New +** → **Blueprint** → conecta este repo
   y elige **tu rama** en el selector de branch.
2. Render lee el `render.yaml` y propone **un web service en plan free**. No
   hay base de datos que crear.
3. La key de Gemini ya viene enlazada desde el env group `gemini-workshop`
   del workspace: no tienes que pegar nada.
4. **Apply** y espera el primer deploy (~2–4 min). El servicio queda en una
   URL tipo `https://tu-usuario-support-agent.onrender.com`.

Con `autoDeploy: true`, cada `git push` a tu rama redeploya solo. Ese es el
ciclo de todos los ejercicios: **edita → commit → push → mira el cambio en
tu URL**.

> **Free tier, dos cosas que vas a notar.** (1) El servicio **se duerme tras
> 15 min sin tráfico** y tarda ~1 min en despertar: si tu URL «no carga»,
> espera y recarga. El facilitador corre un keep-alive durante el workshop
> para que pase lo menos posible. (2) Cada deploy y cada despertar **arranca
> con la memoria vacía**: la ingesta vuelve a correr (unos segundos) y los
> tickets creados antes se pierden. Para el workshop es aceptable.

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
>
> Si el servicio estaba dormido, la primera llamada del cliente MCP puede
> fallar por timeout: abre tu URL en el navegador para despertarlo y
> reintenta.

## Correr en local

```bash
uv sync                                # instala dependencias
cp .env.example .env                   # opcional: pega tu GEMINI_API_KEY (se carga solo)
uv run pytest                          # suite normal (verde desde el inicio)
uv run pytest -m ejercicio             # tu progreso en los ejercicios
uv run python -m support_agent.server  # http://localhost:3000
uv run python -m support_agent.evals   # mini-evals de retrieval
```

Sin `GEMINI_API_KEY` ni `DATABASE_URL`, todo corre en **modo mock**
determinista con la base **en memoria**: sin credenciales, sin Postgres, sin
red. Las respuestas empiezan con `[mock]`, pero el RAG, los tools, los evals
y el MCP funcionan de verdad — ideal para desarrollar.

Para que el servidor recargue solo al guardar un archivo:

```bash
uv run uvicorn support_agent.server:app --reload --port 3000
```

## Variables de entorno

| Var | Requerida | Notas |
| --- | --- | --- |
| `GEMINI_API_KEY` | En Render la aporta el env group `gemini-workshop` | Sin ella, modo mock determinista (local y tests) |
| `AGENT_MODEL` | No | `mock` fuerza el mock aunque haya key |
| `GEMINI_MODEL` | No | Default `gemini-2.5-flash` |
| `GEMINI_EMBED_MODEL` | No | Default `gemini-embedding-001` (768 dims) |
| `DATABASE_URL` | No | Sin ella, backend en memoria (así corre el workshop). Con ella, Postgres + pgvector |
| `PORT` | No | Default `3000` (en Render la inyecta la plataforma) |

En local, la app carga `<raíz>/.env` si existe (sin pisar variables ya
exportadas).

## Variante con Postgres + pgvector

Para que el RAG persista entre reinicios y la query del Ejercicio 2 corra en
pgvector de verdad, agrega una base al `render.yaml` y la variable
`DATABASE_URL` al servicio:

```yaml
projects:
- name: rag-agent-workshop
  environments:
  - name: production
    databases:
    - name: support-agent-db
      plan: free          # o basic-256mb (de pago)
      region: oregon
      postgresMajorVersion: '18'
    services:
    - type: web
      name: support-agent
      # ... igual que ahora ...
      envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: support-agent-db
          property: connectionString
      # ... resto igual ...
```

Al arrancar, la app crea el schema (`CREATE EXTENSION vector`, tablas
`documents`, `chunks`, `orders`, `tickets`) y la ingesta pasa a ser
idempotente entre deploys: solo re-embebe los archivos que cambiaron.

Ojo con el free tier: **solo puede haber una Postgres free por workspace**
y expira a los 30 días. En el workspace compartido del workshop no sirve
(sería una para todos); en tu workspace personal sí. Con plan de pago no hay
límite. La Action `setup-attendee` también prefija la base si la agregas.

## Troubleshooting

| Síntoma | Fix |
| --- | --- |
| El deploy falla en build | Mira los logs: casi siempre es no haber corrido la Action `setup-attendee` (colisión de nombres) o un `render.yaml` editado a mano |
| Mi URL tarda o da timeout | El servicio free estaba dormido: espera ~1 min y recarga. Después responde normal |
| Gemini devuelve 429 (rate limit) | Agrega `AGENT_MODEL=mock` como env var del servicio en Render: todo sigue funcionando en modo mock |
| El chat responde sin fuentes | Es el estado inicial: Ejercicios 1 y 2 |
| «Creé un ticket y desapareció» | Memoria: se pierde al redeployar o al despertar. Esperado en el workshop |
| No encuentra un doc nuevo de `kb/` | En Render, el push redeploya y re-ingesta todo. En local, `curl -X POST http://localhost:3000/api/ingest` sin reiniciar |
| El cliente MCP no conecta | Prueba primero con el Inspector; verifica que la URL termina en `/mcp`; si el servicio dormía, despiértalo desde el navegador y reintenta |
| Nombres colisionan en Render | Corre la Action `setup-attendee` sobre tu rama y vuelve a crear el Blueprint |

## Siguiente paso

Este agente usa el patrón **naive**: todo pasa dentro del request HTTP (mira
el docstring de `src/support_agent/server.py` para saber por qué eso no
escala). Caminos para seguir:

- Persistir el índice y los tickets: [Postgres + pgvector](#variante-con-postgres--pgvector).
- Sacar el trabajo del request: colas + workers, o **Render Workflows**.
- **Retrieval as a tool**: que el modelo decida cuándo buscar en la KB, en
  vez de recuperar siempre.
- **Auth para el servidor MCP** (OAuth/token).
- Más evals: medir también la calidad de la *respuesta* (no solo el
  retrieval), p. ej. con un LLM como juez.
