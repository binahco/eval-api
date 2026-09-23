# eval-api

> **Semana:** 6 · **Core:** `llm-dev-core` 0.6.0

## Problema

Los evals de prompts (test-kit, sem 5) viven como CLI en cada consumidor; si otro
servicio quiere decidir "¿este prompt está en verde?" necesita la misma maquinaria por
HTTP. `eval-api` expone los evals como servicio: `POST /evals/run` corre un dataset
congelado con umbral y `POST /summarize` resume el reporte con un LLM — todo sobre la
base FastAPI LLM-ready de `web-api-base`.

## Demo

```
$ uv run python -m eval_api.main --replay cassettes/ --mode full
{ "prompt_id": "eval-summarizer", "total": 3, "passed": 3, "threshold_ok": true, "cost_usd": "0" }
$ echo $?
0
```

El propio resumidor (`eval-summarizer`) nace evaluado: es el dogfood del conjunto
`test-kit` + `web-api-base`.

## Arquitectura

```
POST /evals/run ──► test-kit (dataset + criterios + umbral) ──► reporte JSON
POST /summarize ─► web-api-base /llm (validez como gate)    ──► resumen validado
       ▲                     │
       │                     └── llm-client (render + validación + retry/reparación)
web-api-base base (health+errores+SSE)            ReplayProvider (CI) · OpenCodeCLI (seed)
```

- `/evals/run` corre cualquier dataset congelado referenciando `eval-summarizer` y
  devuelve el `EvalReport` de test-kit; dataset inválido → 422 `dataset_invalido`.
- `/summarize` llama al prompt `eval-summarizer` (schema `eval-summary-v1`) y el gate
  del core bloquea salidas que no validan (422 `salida_no_validada`).
- `/health`, `/llm` y los errores uniformes vienen de `web-api-base` sin reescribir.

## Recicla de

| Módulo del core | Qué aporta |
|---|---|
| `llm-client` | Llamadas LLM, retry, telemetría, ReplayProvider (D4) |
| `schema-validate` | Salida validada (`eval-summary-v1`) antes de responder |
| `test-kit` | Datasets de caso, runner, umbrales y presupuestos (§8.1) |
| `web-api-base` | FastAPI LLM-ready: factory, /health, /llm, errores y SSE (sem 6) |

## Limitaciones

- HTTP sin auth ni rate-limit: llegan con `auth-base` (sem 25) y `cache-ratelimit`
  (sem 8); `web-api-base` deja el hook (`emitter` y span) pero no agrega.
- `/evals/run` y `/summarize` cubren el caso de un prompt evaluado; evaluar N prompts
  por batch es un paso de `cache-ratelimit`/`cost-obs` a futuro.
- Dataset congelado = snapshot del baseline válido (3 casos); re-baseline es acción
  deliberada, no automática.

## Roadmap

- Sem 8: `cache-ratelimit` aterrizó en `llm-gateway`; reusarlo sobre `/evals/run` cuando el consumo lo pida.
- Sem 39: métricas de costo/latencia por endpoint (`cost-obs`).
- Ampliar dataset congelado a 5+ casos de regresión real.