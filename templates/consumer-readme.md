# {Nombre del proyecto}

> **Semana:** {N} · **Core:** `llm-dev-core` {±core_version}

## Problema

{Qué problema resuelve, en términos del usuario.}

## Demo

{GIF, captura o enlace de la demo.}

## Arquitectura

{Mapa breve: cómo se compone el core con la lógica propia. Un diagrama de bloques, no prosa.}

## Recicla de

| Módulo del core | Qué aporta |
|---|---|
| `llm-client` | Llamadas LLM, retry, streaming, telemetría, ReplayProvider (D4) |
| `schema-validate` | Salida validada antes de entrar al dominio |
| `test-kit` | Datasets de caso, runner, umbrales y presupuestos (§8.1) |
| `web-api-base` | FastAPI LLM-ready: /health, /llm, errores uniformes y SSE (sem. 6) |

## Limitaciones

{Lo que evidentemente no hace. Con honestidad, una lista corta.}

## Roadmap

{Próximos pasos, incl. cualquier issue de retrofit pendiente hacia el core.}