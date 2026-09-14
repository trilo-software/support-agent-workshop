# Guía de Esteban

Workshop de ~2 h 30, nivel introductorio, en dos actos:

- **Acto 1 — RAG**: construir y encender el agente (Ejercicios 1–3 + bonus).
- **Acto 2 — Medir y exponer**: evals (Ejercicio 4) y MCP (Ejercicio 5).

Las dos ideas que la gente debe llevarse (repítelas en el cierre):

1. Un agente con RAG no es magia: trocear docs → guardar embeddings → buscar
   por similitud → inyectar en el prompt → loop de modelo + tools. Y no se
   mejora «a ojo»: se mide con evals.
2. MCP no es magia: es el protocolo estándar para que CUALQUIER cliente
   consuma capacidades que tú construiste. El mismo `retrieve()` sirve al
   agente por HTTP y a Claude por MCP. Y desplegar todo eso es un
   `render.yaml`.

---

## Cómo está montado

Todos trabajan en **ramas del mismo repo** (una por asistente, con su usuario
de GitHub; `main` protegida) y despliegan en **tu workspace de Render**, cada
uno **un web service en plan free, sin base de datos** (RAG en memoria).

Free tier, lo que hay que tener presente: el servicio **se duerme a los 15
min sin tráfico** y tarda ~1 min en despertar; cada deploy y cada despertar
arranca con la memoria vacía (re-ingesta la KB: 7 llamadas de embedding; los
tickets se pierden). El script `scripts/keep_alive.py` pinguea todos los
servicios cada 10 min para que nadie se tope con el arranque en frío en medio
de un ejercicio. Las «free instance hours» del workspace solo se consumen
mientras los servicios están despiertos.

**Al terminar borra los proyectos de los asistentes** (Dashboard → proyecto
→ Settings → Delete project) y, si quieres, sus ramas.

---

## Checklist pre-vuelo (el día antes)

- [ ] Asistentes agregados como **colaboradores** del repo en GitHub (acceso
      de escritura) e invitaciones aceptadas. `main` **protegida** (Settings →
      Branches → require a pull request) para que nadie pushee ahí por error.
- [ ] Invitaciones al workspace de Render enviadas a los asistentes (rol
      **Developer**) y aceptadas: pídeles que creen su cuenta de Render con el
      mismo correo (o con GitHub) antes.
- [ ] Key de Gemini de un proyecto **con billing** (Tier 1), probada:
      `GEMINI_API_KEY=... uv run python -m support_agent.server` y un chat.
- [ ] Env group `gemini-workshop` en el workspace del workshop con la
      `GEMINI_API_KEY` **real** (no un valor provisional). `render.yaml` ya lo
      enlaza con `fromGroup`, así que nadie pega nada. Render exige que el
      grupo exista: si no, el Blueprint falla con *«env var group linkage
      depends on non-existent group»*. Valida con
      `render blueprints validate render.yaml` (CLI de Render, con ese
      workspace activo).
- [ ] Tu **deploy de referencia** funcionando (rama `referencia` + Blueprint
      en el mismo workspace, como un asistente más), y los ejercicios
      resueltos en una rama `soluciones` lista para enseñar.
- [ ] `asistentes.txt` con el usuario de GitHub de cada asistente (uno por
      línea) más la URL de tu deploy de referencia, para el keep-alive:
      `uv run python scripts/keep_alive.py asistentes.txt --once` debe dar
      200 en tu referencia (los demás aún no existen).
- [ ] `npx @modelcontextprotocol/inspector` corre en tu máquina y conecta a
      tu deploy de referencia (`/mcp`).
- [ ] Claude Code instalado y probado con
      `claude mcp add --transport http cafe-pura-vida https://<tu-ref>.onrender.com/mcp`.
- [ ] Proyector: ten abiertas la UI del chat, `/api/debug/search`, los logs
      de Render y una terminal.

## Triage: los primeros 10 minutos

| Síntoma | Fix rápido |
| --- | --- |
| «No puedo crear el Blueprint: nombre en uso» | No corrió la Action `setup-attendee`. Actions → setup-attendee → Run workflow → recrear Blueprint |
| «No veo el workspace de Esteban» | No aceptó la invitación o creó la cuenta con otro correo. Reenviar invitación al correo correcto |
| Build falla con `--frozen` | Tocaron `pyproject.toml` sin regenerar `uv.lock`. `git checkout uv.lock pyproject.toml` |
| Blueprint falla: «non-existent group» | Usas `fromGroup` y el env group no existe en el workspace (o el nombre no coincide). Créalo y reintenta |
| Deploy verde pero el chat da error 500 | La key del env group `gemini-workshop` es inválida o el grupo no quedó enlazado (Service → Environment). Escape: `AGENT_MODEL=mock` |
| La URL tarda ~1 min o da timeout | Servicio free dormido. Esperar y recargar; arrancar el keep-alive si no está corriendo |
| 429 de Gemini por toda la sala | Key saturada: que agreguen `AGENT_MODEL=mock` y sigan; el flujo completo funciona en mock |
| «Run workflow no me deja elegir mi rama» | No hizo push de la rama (`git push -u origin tu-usuario`) o la creó con otro nombre. Recargar la página de Actions |
| `git push` da «permission denied» | No aceptó la invitación de colaborador en GitHub, o intenta pushear a `main` (protegida): que cree su rama |

---

## Run sheet (2 h 30)

Desde el minuto 0, en una terminal aparte:
`uv run python scripts/keep_alive.py asistentes.txt`. Déjalo correr hasta el
cierre (y apágalo al terminar).

| Reloj | Dur | Módulo | Nota |
| --- | --- | --- | --- |
| 0:00 | 15 min | Setup: rama + Action + crear Blueprint | Mientras deploya: dibujar la arquitectura |
| 0:15 | 7 min | Demo del agente «tonto»: responde genérico, sin fuentes, alucina | Motivación de los ejercicios |
| 0:22 | 10 min | Ejercicio 1: el system prompt | push → redeploy → comparar en vivo |
| 0:32 | 15 min | Ejercicio 2: encender el RAG (TOP_K + ORDER BY) | El aha del Acto 1: aparecen las fuentes |
| 0:47 | 10 min | Ejercicio 3: `kb/promociones.md` + ingesta idempotente | «La KB es solo markdown en git» |
| 0:57 | 8 min | Bonus: registrar `check_order_status` | O de buffer si van atrasados |
| 1:05 | 10 min | **Break** | El keep-alive evita que se duerman |
| 1:15 | 25 min | Ejercicio 4: mini-evals + experimentos de top-k y chunking | «Sin evals, cambias a ciegas» |
| 1:40 | 8 min | Intro a MCP: qué es, por qué existe, diagrama cliente/servidor | Anclar con lo que YA construyeron |
| 1:48 | 30 min | Ejercicio 5: completar `buscar_kb` + conectar Inspector/Claude Code | El aha del Acto 2: Claude usa SU RAG |
| 2:18 | 12 min | Cierre: límites del patrón naive, teaser colas/Workflows, se llevan su rama | Exit ticket |

**Flex:** el bonus y el experimento B (chunking) del Ejercicio 4 son
recortables. El Ejercicio 5 **nunca**: es la razón del enfoque MCP. Si el
redeploy de Render va lento en el Ejercicio 5, que se conecten al server
local (`http://localhost:3000/mcp`): desbloquea igual.

---

## Talk track por módulo

### Setup (0:00)

Mientras los deploys corren, dibuja la arquitectura del README en la pizarra.
Puntos: *un* web service (FastAPI) en free, el índice de embeddings **en
memoria** dentro del proceso, y TODO el trabajo del agente pasa dentro del
request HTTP («patrón naive» — planta la semilla del cierre). La ingesta
corre al arrancar y es idempotente por hash. Di en voz alta que el código de
Postgres + pgvector está en el repo y se enciende con `DATABASE_URL` (variante
del README): hoy no lo usamos: en free tier solo hay una Postgres por workspace.

CFU (check for understanding): «¿dónde viven los embeddings?» (en memoria,
como vectores numpy de 768 dims; con Postgres, en la tabla `chunks`, columna
`vector(768)`).

### Demo del agente tonto (0:15)

En tu deploy de referencia SIN resolver: pregunta «¿cuánto tarda el envío a
Cartago?» → genérico, sin chips de fuentes. Pregunta «¿tienen descuento?» →
inventa o no sabe. Mensaje: *el deploy está verde; el agente está mal — y
eso es lo normal en el primer intento de RAG. Hoy lo arreglamos midiendo.*

### Ejercicio 1 (0:22)

Enseña `agent.py` en pantalla: el system prompt + bloque CONTEXTO. La regla
de oro de RAG del lado del prompt: *responde solo con el contexto y cita la
fuente*. Deja 5–6 min de trabajo, luego enseña tu solución.

Pitfall: gente que escribe el prompt en inglés — recuérdales que el test
pide «Pura Vida» y el público habla español.

### Ejercicio 2 (0:32)

EL momento del Acto 1. Explica `<=>` (distancia coseno, menor = más parecido)
y por qué `1 - distancia` es un score legible. El backend en memoria imita la
query (sin ORDER BY tampoco ordena): un fix, dos backends. Antes/después en
vivo con la misma pregunta; señala los chips 📚 con scores.

CFU: «si `<=>` es distancia, ¿el ORDER BY va ASC o DESC?» (ASC — y el score
del SELECT es 1−distancia, por eso mayor = mejor).

### Ejercicio 3 (0:47)

Mensaje: *alimentar la KB no es tocar código, es git*. Tras el push, el log
del deploy muestra `ingesta: 6 documentos, 6 nuevos…` (memoria: cada arranque
embebe todo). Luego la idempotencia en vivo: `curl -X POST
https://<tu-ref>.onrender.com/api/ingest` dos veces seguidas → `ingresados:
0`, cero llamadas de embedding. Si tienes el server local abierto, la versión
vistosa: crea el archivo, `POST /api/ingest` → `ingresados: 1`, sin reiniciar.

### Bonus (0:57)

Un tool = descripción + schema + handler; el agente solo ve el registry.
«¿cómo va mi pedido CR-1003?» antes (no puede) y después (badge 🔧).

### Ejercicio 4 (1:15)

La lección más transferible del workshop: **sin evals, cambias a ciegas**.
Corre la línea base en pantalla, luego `--top-k 1` y `--top-k 8`. Discusión:
más k = más recall pero más tokens y más ruido. El experimento B (chunking)
en parejas si hay tiempo. Cierra con: «¿qué combinación ganó y por qué?» —
no hay respuesta única, ese es el punto: por eso se mide.

Los evals corren en la laptop de cada quien. Sin key en su `.env` usan el
mock (números de referencia abajo); con key, Gemini real y otros números.
Lo que importa es comparar contra su propia línea base.

### Intro a MCP (1:40)

Definición en una frase: *USB-C para capacidades de IA — un protocolo
estándar entre clientes (Claude, IDEs, otros agentes) y servidores (tu
servicio)*. Diagrama: cliente ↔ servidor MCP; el server expone tools con
schemas; el cliente decide cuándo llamarlos leyendo las descripciones.
Ancla: «ya tienen un servidor MCP corriendo en `/mcp` con 2 tools; falta el
mejor: su retrieval».

### Ejercicio 5 (1:48)

La joya. 4 líneas de código y luego la conexión. Orden recomendado: primero
TODOS validan con el Inspector (garantizado), luego Claude Code para el wow.
Antes de que conecten, que cada quien abra su URL en el navegador: así el
servicio está despierto y la primera llamada MCP no muere por timeout.
Cuando Claude responda usando `buscar_kb` de su servicio, di la frase:

> «El mismo `retrieve()` que arreglaron en el Ejercicio 2 lo acaba de usar
> Claude — y ustedes no escribieron ningún endpoint para Claude. Eso es lo
> que estandariza MCP.»

Caveat para decir en voz alta: `/mcp` va sin auth (datos ficticios, solo
lectura); en producción, OAuth/token.

### Cierre (2:18)

Límites del naive: timeouts, deploys que pierden trabajo en vuelo, sin
concurrencia real (léelo del docstring de `server.py`). Y el límite de hoy:
el índice en memoria muere con cada reinicio — primer paso real hacia
producción: Postgres + pgvector (ya está en el código). Teaser: colas +
workers / Render Workflows. Extensiones: retrieval-as-a-tool, auth MCP,
evals de respuesta con LLM-juez. Se llevan su rama completa funcionando (y
pueden hacer fork del repo para conservarla).

Exit ticket (2 preguntas): «¿qué pieza de RAG te sorprendió por simple?» y
«¿qué conectarías por MCP en tu trabajo?».

---

## Soluciones

### Ejercicio 1 — `src/support_agent/prompts.py`

```python
SYSTEM_PROMPT = """Eres el agente de soporte al cliente de Café Pura Vida, una
tienda online de café de especialidad costarricense con suscripciones
mensuales. Respondes siempre en español, con tono cercano y profesional.

Reglas:
1. Responde ÚNICAMENTE con la información del bloque CONTEXTO de este prompt.
   No inventes políticas, precios ni plazos que no aparezcan ahí.
2. Cita la fuente de cada dato entre corchetes con el título del documento,
   por ejemplo: [Envíos] o [Suscripciones].
3. Si el CONTEXTO no alcanza para responder con seguridad, admítelo con
   honestidad y ofrece escalar el caso a un humano.
4. Usa los tools disponibles cuando ayuden: consultar un pedido por su número
   (formato CR-1234) o escalar a un humano creando un ticket.
5. Sé breve: dos o tres frases suelen bastar.
"""
```

(Cualquier prompt que cumpla las 4 reglas del test sirve.)

### Ejercicio 2 — `src/support_agent/rag.py`

```python
TOP_K = 4
```

```sql
SELECT c.content, d.title, d.source,
       1 - (c.embedding <=> $1::vector) AS score
FROM chunks c JOIN documents d ON d.id = c.document_id
ORDER BY c.embedding <=> $1::vector
LIMIT $2;
```

### Ejercicio 3 — `kb/promociones.md` (ejemplo)

```markdown
# Promociones

Promociones y descuentos vigentes de Café Pura Vida.

## Descuento de primera compra

Todo cliente nuevo tiene un 15 % de descuento en su primera compra con el
código **BIENVENIDA15**. Aplica a bolsas individuales y a la caja
degustación; no aplica al primer mes de una suscripción. No es acumulable.

## Programa de referidos

Si un cliente refiere a un amigo con su enlace personal:

- El amigo recibe ₡3.000 de descuento en su primer pedido.
- El cliente que refiere recibe ₡3.000 de crédito al entregarse ese pedido.

El crédito por referidos no vence y acumula hasta ₡30.000 por año.

## Promociones de temporada

- Semana del café (última semana de setiembre): 2x1 en la caja degustación.
- Diciembre: envío gratis en todos los pedidos, sin monto mínimo.
```

### Ejercicio 4

No tiene solución de código. Resultados de referencia con el mock (para que
sepas qué esperar en pantalla):

- Estado inicial del repo (`TOP_K = 0`): `0/11 hits` — buen «antes».
- Resuelto, `top_k=4`: `11/11 hits · 10/11 hit@1`.
- `--top-k 1`: `10/11 hits · 10/11 hit@1` (menos recall).
- `--top-k 8`: `11/11 hits` (igual, pero el CONTEXTO se duplica en tamaño).

### Ejercicio 5 — `src/support_agent/mcp_server.py`

```python
@mcp.tool(
    description=(
        "Busca en la base de conocimiento de Café Pura Vida (envíos, "
        "suscripciones, facturación, productos, devoluciones) y devuelve los "
        "fragmentos más relevantes para una pregunta, con fuente y score."
    )
)
async def buscar_kb(pregunta: str, top_k: int = 4) -> list[dict]:
    chunks = await retrieve(pregunta, top_k=top_k)
    return [
        {
            "titulo": c.title,
            "fuente": c.source,
            "score": round(c.score, 3),
            "contenido": c.content,
        }
        for c in chunks
    ]
```

### Bonus — `src/support_agent/tools/__init__.py`

```python
TOOLS: dict[str, Tool] = {
    escalate_to_human.tool.name: escalate_to_human.tool,
    check_order_status.tool.name: check_order_status.tool,
}
```

---

## Notas operativas

- **Modelos**: defaults `gemini-3.6-flash` y `gemini-embedding-001` (vigentes
  a set-2026; `gemini-2.5-flash` ya no está disponible para proyectos nuevos
  de Google). Ambos son configurables por env var; otro Gemini 3 (p. ej.
  `GEMINI_MODEL=gemini-3.8-flash`) funciona igual. Los Gemini 3 exigen
  devolver el `thought_signature` en tool calling: el agente ya lo hace
  (`raw_content` en `model.py`). NO cambies `GEMINI_EMBED_MODEL` a mitad de
  workshop: otro modelo = otro espacio de embeddings = re-ingestar todo.
- **Mock como red de seguridad**: TODO el workshop (incluido MCP) funciona
  con `AGENT_MODEL=mock`. Si Gemini se cae o los 429 arrecian, el show sigue.
- **Keep-alive**: `scripts/keep_alive.py` solo usa la biblioteca estándar;
  acepta usuarios de GitHub o URLs completas, y `--once` para probar. Apágalo
  al terminar: mientras corre, los 18 servicios consumen free instance hours.
- **Sesiones MCP y spin-down**: el servidor MCP es `stateless_http`, así que
  un despertar no invalida nada; solo la primera llamada puede dar timeout.
  Reintentar.
- **Postgres + pgvector**: variante en el README, validada con `render
  blueprints validate`. En el workspace compartido no sirve en free (una sola
  Postgres free por workspace); si algún día quieres bases para todos, tienen
  que ser de pago (una por asistente): bórralas al terminar.
