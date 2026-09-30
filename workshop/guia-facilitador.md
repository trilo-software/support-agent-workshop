# Guía de Esteban

Workshop de ~3 h, nivel introductorio, en dos actos y siete ejercicios
(ninguno es «bonus»: todos cuentan y todos tienen test rojo→verde):

- **Acto 1 — Construir**: prompt, RAG, KB y tools (Ejercicios 1–5). Cierra
  con el agente completo: sabe quién es, busca en la KB y actúa.
- **Acto 2 — Medir y exponer**: evals (Ejercicio 6) y MCP (Ejercicio 7).

Las dos ideas que la gente debe llevarse (repítelas en el cierre):

1. Un agente con RAG no es magia: trocear docs → guardar embeddings → buscar
   por similitud → inyectar en el prompt → loop de modelo + tools. Y no se
   mejora «a ojo»: se mide con evals.
2. Un tool son tres cosas (descripción, schema, handler) y una regla: el
   modelo extrae los argumentos, el código decide. Precios, plazos y
   políticas nunca los calcula el modelo.
3. MCP no es magia: es el protocolo estándar para que CUALQUIER cliente
   consuma capacidades que tú construiste. El mismo `retrieve()` sirve al
   agente por HTTP y a otro agente por MCP. Y desplegar todo eso es un
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
- [ ] `uv run python scripts/preguntar_por_mcp.py https://<tu-ref>.onrender.com/mcp`
      contra tu referencia con el Ejercicio 7 resuelto: Gemini debe llamar
      `buscar_kb` y responder con la KB. Es el wow de toda la sala.
- [ ] La key de Gemini lista para compartirla por chat el día del workshop
      (los asistentes la pegan en su `.env` para el script). Bórrala en AI
      Studio al terminar y crea otra.
- [ ] Claude Code instalado y probado con
      `claude mcp add --transport http cafe-pura-vida https://<tu-ref>.onrender.com/mcp`
      (lo muestras tú desde el proyector: requiere cuenta de pago).
- [ ] Opcional: Gemini CLI (`npx @google/gemini-cli`) con
      `mcp add -t http cafe_pura_vida <url>`; gratis con cuenta de Google.
      Pruébalo antes si lo vas a ofrecer: no está validado en este repo.
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

## Run sheet (~3 h)

Desde el minuto 0, en una terminal aparte:
`uv run python scripts/keep_alive.py asistentes.txt`. Déjalo correr hasta el
cierre (y apágalo al terminar).

| Reloj | Dur | Módulo | Nota |
| --- | --- | --- | --- |
| 0:00 | 15 min | Setup: rama + Action + crear Blueprint | Mientras deploya: dibujar la arquitectura |
| 0:15 | 7 min | Demo del agente «tonto»: sin fuentes, escala todo a un humano | Motivación de los ejercicios |
| 0:22 | 10 min | Ejercicio 1: el system prompt | push → redeploy → comparar en vivo |
| 0:32 | 15 min | Ejercicio 2: encender el RAG (TOP_K + ORDER BY) | El aha del Acto 1: aparecen las fuentes |
| 0:47 | 10 min | Ejercicio 3: `kb/promociones.md` + ingesta idempotente | «La KB es solo markdown en git» |
| 0:57 | 8 min | Ejercicio 4: registrar `check_order_status` | Anatomía de un tool: descripción + schema + handler |
| 1:05 | 20 min | Ejercicio 5: tu propio tool `calcular_envio` | «El modelo extrae, el código decide» |
| 1:25 | 10 min | **Break** | El keep-alive evita que se duerman |
| 1:35 | 30 min | Ejercicio 6: 2 preguntas doradas + experimentos de top-k y chunking | «Sin evals, cambias a ciegas» |
| 2:05 | 8 min | Intro a MCP: qué es, por qué existe, diagrama cliente/servidor | Anclar con lo que YA construyeron |
| 2:13 | 30 min | Ejercicio 7: completar `buscar_kb` + Inspector + script de Gemini | El aha del Acto 2: otro agente usa SU RAG |
| 2:43 | 12 min | Cierre: límites del patrón naive, teaser colas/Workflows, se llevan su rama | Exit ticket |

**Flex:** ningún ejercicio es opcional. Si el grupo va lento, lo primero que
se recorta es el experimento B (chunking) del Ejercicio 6 y el paso extra de
MCP del 7 (exponer `calcular_envio`). El Ejercicio 7 en sí **nunca**: es la
razón del enfoque MCP. Si el redeploy de Render va lento en el Ejercicio 7,
que se conecten al server local (`http://localhost:3000/mcp`) con el
Inspector: desbloquea igual.

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
Cartago?» → sin chips de fuentes, y con Gemini 3.6 lo típico es que **escale
todo a un humano** (badge 🔧 `escalate_to_human`, ticket #1, #2, #3…) porque
no tiene contexto; otras veces responde genérico o inventa. Pregunta
«¿tienen descuento?» → lo mismo. Mensaje: *el deploy está verde; el agente
está mal — y eso es lo normal en el primer intento de RAG. Hoy lo arreglamos
midiendo.*

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

Pitfall real (pasó en la prueba piloto): escribir el `ORDER BY` **dentro del
SELECT**, `1 - (ORDER BY c.embedding <=> $1::vector) AS score`. Es SQL
inválido en Postgres; el backend en memoria ya no lo da por bueno y el test
lo dice con todas las letras: la cláusula va entre el JOIN y el LIMIT.

### Ejercicio 3 (0:47)

Mensaje: *alimentar la KB no es tocar código, es git*. Tras el push, el log
del deploy muestra `ingesta: 6 documentos, 6 nuevos…` (memoria: cada arranque
embebe todo). Luego la idempotencia en vivo: `curl -X POST
https://<tu-ref>.onrender.com/api/ingest` dos veces seguidas → `ingresados:
0`, cero llamadas de embedding. Si tienes el server local abierto, la versión
vistosa: crea el archivo, `POST /api/ingest` → `ingresados: 1`, sin reiniciar.

### Ejercicio 4 (0:57)

Abre `check_order_status.py` en pantalla y señala las tres partes: la
descripción (lo que el modelo lee para decidir), el schema (lo que tiene que
extraer del mensaje) y el handler (código). Luego `tools/__init__.py`: el
agente solo ve lo que está en `TOOLS`. «¿cómo va mi pedido CR-1003?» antes
(no puede: se lo inventa o escala) y después (badge 🔧 y datos reales).

CFU: «¿qué pasa si la descripción dice “consulta pedidos” pero el schema
no pide el número?» (el modelo llama al tool sin argumentos y falla: los
tres pedazos tienen que coincidir).

### Ejercicio 5 (1:05)

La lección más importante del Acto 1 y la más transferible a su trabajo:
**el modelo extrae los argumentos; el código decide**. Antes del ejercicio,
pregunta en tu referencia «¿cuánto me sale un pedido de ₡12.000 a
Turrialba?»: el modelo lee `envios.md` y hace la cuenta; a veces acierta, a
veces no, y nunca puedes garantizarlo. Después: badge 🔧 `calcular_envio`,
₡2.500 y 2 a 3 días, siempre.

Deja 12–14 minutos de trabajo. Los dos atascos típicos: (1) el handler
devuelve bien pero el modelo no lo llama → la descripción no dice cuándo
usarlo, o no está en `TOOLS`; (2) «Limón» no matchea → no normalizaron
tildes (`_normalizar` ya viene hecho, hay que usarlo).

Cierra con la pregunta que conecta con su vida real: «¿qué cálculo o
política de su negocio hoy la está haciendo un modelo cuando debería
hacerla código?».

### Ejercicio 6 (1:35)

**Sin evals, cambias a ciegas**. Corre la línea base en pantalla. Luego el
entregable: cada quien agrega dos preguntas doradas (una de promociones) y
vuelve a correr; si no aparecen, afinan la pregunta o el documento. Ese
ciclo, escribir el caso → medir → ajustar, es el trabajo real de mantener un
RAG. Después `--top-k 1` y `--top-k 8`. Discusión: más k = más recall pero
más tokens y más ruido. El experimento B (chunking) en parejas. Cierra con:
«¿qué combinación ganó y por qué?» — no hay respuesta única, ese es el
punto: por eso se mide.

Los evals corren en la laptop de cada quien. Sin key en su `.env` usan el
mock (números de referencia abajo); con key, Gemini real y otros números.
Lo que importa es comparar contra su propia línea base.

### Intro a MCP (2:05)

Definición en una frase: *USB-C para capacidades de IA — un protocolo
estándar entre clientes (Claude, IDEs, otros agentes) y servidores (tu
servicio)*. Diagrama: cliente ↔ servidor MCP; el server expone tools con
schemas; el cliente decide cuándo llamarlos leyendo las descripciones.
Ancla: «ya tienen un servidor MCP corriendo en `/mcp` con 2 tools; falta el
mejor: su retrieval».

### Ejercicio 7 (2:13)

La joya. 4 líneas de código y luego la conexión. Orden recomendado: primero
TODOS validan con el Inspector (garantizado); luego el wow para toda la sala
con `scripts/preguntar_por_mcp.py`: la API de Gemini se conecta a SU
servidor y llama `buscar_kb` sola. Claude Code lo muestras tú desde el
proyector, porque requiere cuenta de pago. Antes de que conecten, que cada
quien abra su URL en el navegador: así el servicio está despierto y la
primera llamada MCP no muere por timeout. Cuando Gemini (o Claude) responda
usando `buscar_kb` de su servicio, di la frase:

> «El mismo `retrieve()` que arreglaron en el Ejercicio 2 lo acaba de usar
> otro agente — y ustedes no escribieron ningún endpoint para él. Eso es lo
> que estandariza MCP.»

Si sobra tiempo, el paso extra: exponer `calcular_envio` por MCP (tres
líneas) y preguntarle a Gemini por el script «¿cuánto cuesta enviar un pedido
de 12000 a Limón?». El tool que escribieron en el 5 lo usa otro agente.

Caveat para decir en voz alta: `/mcp` va sin auth (datos ficticios, solo
lectura); en producción, OAuth/token.

### Cierre (2:43)

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

### Ejercicio 4 — `src/support_agent/tools/__init__.py`

```python
TOOLS: dict[str, Tool] = {
    escalate_to_human.tool.name: escalate_to_human.tool,
    check_order_status.tool.name: check_order_status.tool,
}
```

### Ejercicio 5 — `src/support_agent/tools/calcular_envio.py`

```python
async def handler(canton: str, monto_pedido: int) -> dict:
    zona = ZONAS.get(_normalizar(canton))
    if zona is None:
        return {
            "error": (
                f"No conozco el cantón {canton!r}. Zonas de envío: GAM (San José, "
                "Heredia, Alajuela centro, Cartago centro), Regional (resto de "
                "Alajuela y Cartago, Grecia, San Ramón, Turrialba, Puriscal) y "
                "Extendida (Limón, Puntarenas, Guanacaste, Zona Sur y Zona Norte). "
                "Pregunta al cliente por su cantón."
            )
        }
    tarifa = TARIFAS[zona]
    gratis = monto_pedido > ENVIO_GRATIS_DESDE
    return {
        "canton": canton,
        "zona": zona,
        "costo": 0 if gratis else tarifa["costo"],
        "envio_gratis": gratis,
        "dias_habiles": tarifa["dias_habiles"],
    }


tool = Tool(
    name="calcular_envio",
    description=(
        "Cotiza el envío de un pedido de Café Pura Vida: dado el cantón de "
        "entrega y el monto del pedido en colones, devuelve la zona (GAM, "
        "Regional o Extendida), el costo del envío (0 si aplica envío gratis "
        "por superar ₡25.000) y los días hábiles de entrega. Úsalo siempre que "
        "el cliente pregunte cuánto cuesta o cuánto tarda un envío a un lugar "
        "concreto; no calcules el costo tú mismo."
    ),
    parameters={
        "type": "object",
        "properties": {
            "canton": {
                "type": "string",
                "description": "Cantón o lugar de entrega, por ejemplo Heredia, Turrialba o Limón",
            },
            "monto_pedido": {
                "type": "integer",
                "description": "Monto del pedido en colones, sin puntos ni símbolos, por ejemplo 12000",
            },
        },
        "required": ["canton", "monto_pedido"],
    },
    handler=handler,
)
```

Y en `tools/__init__.py`, la tercera línea del registry:
`calcular_envio.tool.name: calcular_envio.tool,`.

### Ejercicio 6 — `evals/preguntas.yaml` (ejemplo de preguntas nuevas)

```yaml
- pregunta: "¿Cómo funciona el programa de referidos?"
  fuente_esperada: kb/promociones.md

- pregunta: "¿Qué molienda me recomiendan para prensa francesa?"
  fuente_esperada: kb/productos.md
```

Resultados de referencia con el mock (para que sepas qué esperar en
pantalla), con las 11 preguntas originales:

- Estado inicial del repo (`TOP_K = 0`): `0/11 hits` — buen «antes».
- Resuelto, `top_k=4`: `11/11 hits · 10/11 hit@1`.
- `--top-k 1`: `10/11 hits · 10/11 hit@1` (menos recall).
- `--top-k 8`: `11/11 hits` (igual, pero el CONTEXTO se duplica en tamaño).
- Con las dos preguntas de ejemplo de arriba (13 en total): `13/13 hits ·
  12/13 hit@1`.

### Ejercicio 7 — `src/support_agent/mcp_server.py`

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

Paso extra del Ejercicio 7 (exponer `calcular_envio` por MCP):

```python
from .tools import calcular_envio as calcular_envio_tool


@mcp.tool(description=calcular_envio_tool.tool.description)
async def calcular_envio(canton: str, monto_pedido: int) -> dict:
    return await calcular_envio_tool.handler(canton=canton, monto_pedido=monto_pedido)
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
