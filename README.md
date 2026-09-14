# Coldline Task 2.7 — Controlled retrieval experiment

This checkpoint includes the completed authorization composition: retrieval enforces both tenant
and classification before dense and sparse candidates are fetched. `poe authorization-checkpoint`
checks both exclusions and permitted retrieval against the running, ingested stack; `poe verify`
rebuilds the stack and includes that check.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/tripleten-com/ai-system-engineering-curriculum-sprint-2-task-2-7/tree/main)

## Start the system

Prerequisites are Python 3.12 and Docker with Compose v2. The supplied bootstrap supports macOS
arm64/x86-64, Windows x86-64, and Linux x86-64/aarch64, and installs pinned uv 0.11.8 under
`.tools/bin`. If your computer cannot run the stack locally, use the Codespaces button above.

On macOS and most Linux distributions the interpreter is `python3`; substitute it wherever these
commands say `python`.

```shell
python infra/scripts/bootstrap.py
./.tools/bin/uv sync --frozen
./.tools/bin/uv run --frozen poe preflight
./.tools/bin/uv run --frozen poe start
./.tools/bin/uv run --frozen poe ready
./.tools/bin/uv run --frozen poe ingest
./.tools/bin/uv run --frozen poe baseline
```

PowerShell and POSIX wrappers are available under `infra/scripts/`. After uv is on `PATH`, the
shorter `uv run --frozen poe <task>` form works.

| Service | Local URL | Purpose |
|---|---|---|
| API | `http://localhost:8000` | Submit exception workflows and retrieval queries |
| Grafana | `http://localhost:3000` | Use the focused diagnostics dashboard |
| Prometheus | `http://localhost:9090` | Query bounded metrics |
| Jaeger | `http://localhost:16686` | Inspect local traces |
| LocalStack S3 | `http://localhost:4566` | Inspect the emulated object-storage endpoint |

Each of these ports can be overridden by setting the matching `COLDLINE_API_HOST_PORT`,
`COLDLINE_GRAFANA_HOST_PORT`, `COLDLINE_PROMETHEUS_HOST_PORT`, `COLDLINE_JAEGER_HOST_PORT`, or
`COLDLINE_LOCALSTACK_HOST_PORT` environment variable in your shell environment or a local `.env`
file (copy `.env.example`) if a default collides with something already running on your machine.
Keep the override in place for every `poe` command.

If you change the API port, also set `COLDLINE_API_HOST_PORT` in the shell that runs
`poe load-test`: this command does not read `.env`. Use the same port for startup and load testing.
For example, to use port 8001, run the command for your shell before starting the system:

| Shell | Set the API host port |
|---|---|
| PowerShell | `$env:COLDLINE_API_HOST_PORT = "8001"` |
| macOS/Linux (POSIX) | `export COLDLINE_API_HOST_PORT=8001` |

PostgreSQL, Redis, worker metrics, and OTLP remain inside the Compose network. Codespaces uses the
same `compose.yaml` and keeps every forwarded port private.

## Command path

For a fresh investigation, run the supplied commands in this order:

```text
poe start
poe ready
poe ingest
poe baseline
poe verify
```

| Command | Use |
|---|---|
| `poe ingest` | Run the supplied baseline corpus ingestion inside the API container |
| `poe baseline` | Run every published query and print the baseline evaluation report |
| `poe benchmark-baseline` | Measure the supplied baseline arm and retain `.benchmark/baseline.json` |
| `poe benchmark-experiment` | Measure your configuration and retain `.benchmark/experiment.json` |
| `poe compare` | Read both retained reports, compare with the cached judge evidence, apply the published rule |
| `poe benchmark-reproduce` | Re-measure both arms and print the drift; writes nothing, grades nothing |
| `poe report-contract` | Check that an invalid or missing retained report fails validation |
| `poe experiment` | Rebuild, ingest, then run this Task's experiment checks |
| `poe migrate` | Apply every migration inside the API container |
| `poe migrate-current` | Print the revision the database is stamped at |
| `poe migrate-down` | Roll back the most recent migration |
| `poe student-tests` | Run your own tests under `tests/student/` |
| `poe unit` | Run fast isolated behavior tests |
| `poe contract` | Check interfaces, boundaries, submissions, and repository structure |
| `poe smoke` | Check the initialized running platform |
| `poe e2e` | Run the external API-to-worker workflow |
| `poe verify` | Run the public student verification path |
| `poe scenario` | Run the supplied exception-workflow walkthrough |
| `poe load-test` | Run this repository's supplied traffic profile |
| `poe reset-baseline` | Clear exception and Redis data, then restart the worker between load runs |
| `poe restart` | Restart the existing API and worker containers **without rebuilding**; run `poe start` instead after editing source |
| `poe stop` | Remove containers and the network, keeping named volumes |
| `poe reset` | Remove containers, the network, and local named volumes |

`poe ingest` is idempotent: running it twice produces the same rows, the same counts, and the same
corpus digest. `poe reset` removes the database volume, so run `poe ingest` again after a reset.

For Task 2.7, `poe verify` rebuilds and starts the stack, ingests the supplied corpus, then runs
readiness, smoke tests, the end-to-end exception workflow, the answer-sheet checks, the experiment
checks, and your own tests under `tests/student/`.

`poe verify` begins with `poe start`, which is `up --build --wait`, so the container the checks
measure is built from your checkout rather than from a previous one.

The experiment harness captures one arm per command and retains one report per capture:
`poe benchmark-baseline` writes `.benchmark/baseline.json` and `poe benchmark-experiment` writes
`.benchmark/experiment.json`. Neither writes the other, and neither overwrites its own report
without `--recapture`.

**Both reports are committed.** They are required run artifacts, not scratch output: every numeric
answer is graded against them at the published precision, `poe compare` reads them instead of
re-measuring, and the CMS grading integration reads them too. A missing or invalid report fails
validation rather than becoming a decision. `docs/contracts/benchmark-report.schema.json` is the
contract they are validated against, and `poe benchmark-reproduce` re-measures without touching
them.

## Folder map

```text
repository root/
├── docs/                Student guidance, public contracts, and fidelity notes
│   ├── contracts/       Machine-readable public contracts
│   ├── fidelity/        Local-runtime boundary notes
│   ├── retrieval/       Supplied retrieval pipeline reference
│   └── student/         This Task's student contract
├── config/              Retrieval configuration
│   └── student/         The one configuration file you may change
├── infra/               Local setup and runtime configuration
│   ├── corpus/          Supplied synthetic corpus, custody record, and query set
│   ├── judge/           Supplied cached judge evidence and its provenance record
│   └── postgres/        Database initialization and the migration baseline stamp
├── loadtest/            Supplied traffic profile and provider-latency harness
├── migrations/          Alembic environment, revision template, and revisions
│   └── versions/        The supplied baseline revision, and the one you write
├── src/
│   ├── api/             HTTP application code, the retrieval and document paths, composition
│   ├── worker/          Background application code
│   ├── domain/          Shared domain code, contracts, service and repository contracts
│   ├── ports/           Application interfaces
│   └── adapters/        Technology-specific implementations
└── tests/
    ├── unit/            Isolated behavior checks
    ├── benchmark/       Supplied evaluation harness, metrics, retained reports, and the rule
    ├── contract/        Interface, retrieval, experiment, and repository checks
    ├── doubles/         Supplied deterministic test doubles
    ├── student/         Your own tests, including this Task's regression test
    ├── smoke/           Running-platform checks
    └── e2e/             Supplied workflow tools and checks
```

## Overview

Use the Task 2.7 lesson to decide what to do. This README covers local setup and repository
orientation.

1. `README.md` — local setup, commands, and permitted changes.
2. [`docs/student/task-2-7-contract.md`](docs/student/task-2-7-contract.md) — the approved
   parameters, how latency is measured, the two retained reports, the published decision rule,
   and where each check looks.
3. `config/retrieval-baseline.yaml` — the control arm, protected.
4. `config/student/retrieval.yaml` — the one file you change.
5. `infra/judge/README.md` — what the cached judge evidence is, how it was derived, and why it is
   comparison-only.
6. `tests/benchmark/` — the supplied harness: configuration validation, metrics, arm capture and
   report retention, the comparison, and the published decision rule.
7. `tests/regression.py` — the helper your regression test asserts through.

The application source lives in five flat packages:

| Package | Responsibility |
|---|---|
| `api` | HTTP delivery, API use cases, the retrieval workflow, versioned routes, configuration, and composition |
| `worker` | Background processing, retries, configuration, and composition |
| `domain` | Provider-neutral contracts, state rules, identity, redaction, embedding, chunking, fusion, access constraints, service and repository contracts |
| `ports` | Exactly five visible application interfaces |
| `adapters` | PostgreSQL, pgvector retrieval, Redis Streams, S3-compatible object storage, deterministic model, logs, traces |

`src/api/bootstrap.py` and `src/worker/bootstrap.py` compose each process from its settings and
adapters. Process settings live in `src/api/config.py` and `src/worker/config.py`; other modules
receive settings or collaborators through function and constructor arguments.

## Inspect database and object-store evidence

After `poe ingest`, use the PostgreSQL client already installed in the supplied container.
These read-only commands show the table definitions and the stored chunk representations:

```shell
docker compose exec -T postgres psql -U coldline -d coldline -c "\d documents"
docker compose exec -T postgres psql -U coldline -d coldline -c "\d chunks"
docker compose exec -T postgres psql -U coldline -d coldline -c "SELECT chunk_id, document_id, chunk_index, vector_dims(embedding), search_document, tenant_id, access_tier FROM chunks ORDER BY chunk_id;"
```

Compare the results with `infra/postgres/002_retrieval_corpus.sql` and the supplied corpus
fixtures. From Task 2.6 onward, also compare `poe migrate-current` and the files in
`migrations/versions/` with the live schema. For object-store evidence, use `GET /api/v1/corpus/objects?prefix=corpus/`
at the API URL above and inspect `docker compose logs localstack`. The initializer provisions
resources and uploads the supplied objects; `poe ingest` loads the searchable database rows.
Use the Task lesson to decide which observations to collect and which changes are permitted.

## The five ports

Find the available interfaces in `src/ports/`. A port describes an application capability; an
adapter provides it using a concrete technology. Determine which ports are active from your own
runtime evidence rather than from this guide.

| Port | General responsibility |
|---|---|
| `ModelProvider` | Call an AI model service |
| `Retriever` | Look up relevant context or documents |
| `ObjectStore` | Store large binary objects or files |
| `JobQueue` | Publish and consume background work |
| `SecretProvider` | Read API keys and credentials |

## The experiment

Two configurations, one golden evaluation set, one changed parameter.

```text
config/retrieval-baseline.yaml   the control arm, protected
config/student/retrieval.yaml    the experimental arm, yours
```

The harness reads both files and measures each arm against the identical golden set, back to back,
against one already-running stack. Both arms state their parameters per request through the
supplied evaluation endpoint, so neither side of the comparison pays a restart cost the other
avoids.

```text
POST /api/v1/experiments/retrieval
  {"query_id": "...", "text": "...",
   "authorization": {"tenant_id": "...", "clearance": "standard"},
   "top_k": 3, "fusion_weight": 0.5}
  -> the fused ranking, its per-stage evidence, and the parameters applied
```

That endpoint is an evaluation surface, supplied and protected. It exists so two configurations can
be measured under identical conditions. `POST /api/v1/retrieval/search` keeps its own composed
defaults and takes no parameters from callers: tuning knobs do not belong on a product API.

Quality is measured two ways, and only one of them is authoritative. See
[`docs/student/task-2-7-contract.md`](docs/student/task-2-7-contract.md) and
[`infra/judge/README.md`](infra/judge/README.md).

## Schema ownership

Two mechanisms create schema in this repository, and they do not overlap.

| Mechanism | What it owns | When it runs |
|---|---|---|
| `infra/postgres/0*.sql` | The initialized schema: `exceptions`, `documents`, `chunks`, `idempotency_claims`, and the `alembic_version` stamp | The initializer, on every start, idempotently |
| `migrations/versions/` | Every change made *after* that point | `poe migrate`, on request |

The baseline revision is empty on purpose: it names the schema as initialized, and it is where a
rollback stops. From this Task the initializer also runs `alembic upgrade head` on every start, so
the service never serves traffic against a schema older than the code in this repository. Both
`infra/postgres/` and `migrations/` are protected here; Task 2.6's reference migration is supplied
and already applied.

## Document API

The document surface and the repository behind it are supplied.

```text
POST /api/v1/documents                        -> persist one document and its chunks atomically
GET  /api/v1/documents?tenant_id=&clearance=  -> list the documents one scope may read
GET  /api/v1/documents/{id}?tenant_id=&clearance=         -> one document, or 404 when out of scope
GET  /api/v1/documents/{id}/chunks?tenant_id=&clearance=  -> that document's readable chunks
```

## Versioned API

Version 1 and the version 2 document endpoint are both supplied from this Task onward.

```text
POST /api/v2/documents   DocumentV2Request  -> DocumentV2Response
```

The reference version 2 endpoint from Task 2.5 is composed for you here. Your own Task 2.5
implementation — of either supported operation — stays in that Task's pull request.

## Retrieval API

Both endpoints are supplied and are not student work.

```text
POST /api/v1/retrieval/search
  {"query_id": "...", "text": "...",
   "authorization": {"tenant_id": "...", "clearance": "standard"},
   "explain": false}
  -> ranked results, per-stage evidence, prompt context, citations

GET  /api/v1/corpus/objects?prefix=corpus/
  -> the object keys visible through the published ObjectStore port
```

Set `"explain": true` to add the authorization stage's readable pool to the evidence. That costs
one extra query, so ordinary requests leave it off.

## Test levels

| Level | Requires Compose | Main question |
|---|---:|---|
| Unit | No | Does one responsibility behave correctly, including failures? |
| Contract | Some | Do interfaces, schemas, paths, and dependency rules stay compatible? |
| Smoke | Yes | Did the complete local platform initialize and become observable? |
| E2E | Yes | Can an external client complete the supplied workflow? |

Contract checks marked `runtime` need the running stack. `poe contract` skips them; `poe verify`
and `poe runtime-contract` run them.

## Submission checks

Run `poe verify` locally before opening your student pull request. Public GitHub CI repeats
the student checks. The course platform (CMS) runs the required protected grading separately
and associates its results with your submission commit. A green template-export check, or a
skipped student check on an `export/` branch, is not a passing grade. You do not configure
GitHub grading secrets. Follow the Task lesson's instructor-review and progression policy.

## Task boundary

Task 2.7 asks you to change **exactly one** approved retrieval parameter, measure both
configurations against the same golden evaluation set, compare the authoritative deterministic
metric with the comparison-only cached judge evidence, add one regression test for a query your
change affected, and record the decision the supplied policy gives. Use the supplied policy: B = 14.0 ms and T = 3.8 ms. Keep both reports and record the
decision calculated from your measurements; do not edit the supplied constants.

The harness, the golden set, the labels, the cached judge evidence, and the decision rule are all
supplied. What you contribute is one parameter value, one regression test, two retained reports,
and eight recorded answers.

The decision is not a judgment call. One rule is published in `config/adoption-policy.yaml`, and it
gives exactly one answer for a valid comparison — see
[`docs/student/task-2-7-contract.md`](docs/student/task-2-7-contract.md). Its two constants, the
latency budget `B` and the latency tolerance `T`, are calibrated and published by the benchmark
owner before release. **For this local release, B = 14.0 ms and T = 3.8 ms.** The supplied policy records the
calibration method and environment. `poe compare` calculates the decision from your retained
reports. A missing or unpublished policy in a mismatched template remains an infrastructure
error: retain the reports and contact support; do not guess a fallback answer.

These paths are student-editable:

- `config/student/retrieval.yaml`
- anything you add under `tests/student/`
- `submission.yaml`

These two are permitted in your pull request but are generated by the harness rather than edited:

- `.benchmark/baseline.json`
- `.benchmark/experiment.json`

`config/adoption-policy.yaml`, `config/benchmark-template.yaml`, `config/retrieval-baseline.yaml`,
`infra/corpus/`, `infra/judge/`, `tests/benchmark/`, `tests/regression.py`, `tests/golden.py`,
`migrations/`, and the whole of `src/` are protected.

The baseline configuration is `top_k = 3` and `fusion_weight = 0.5`. Each arm returns a fixed
candidate pool of 12 rows before fusion, so the two parameters change what fusion selects without
changing what the arms see. That is also why `top_k` cannot exceed 12.

### Student walkthrough

See **Task 2.7: Controlled retrieval experiment** in your course platform for the full walkthrough.
In outline: start the stack and ingest the corpus, run `poe benchmark-baseline` before changing
anything and record its recall and p95 from the retained report, change exactly one parameter in
`config/student/retrieval.yaml`, run `poe benchmark-experiment` and record the experimental figures
the same way, run `poe compare` to read the judge comparison and the published rule, record the
classification and your decision, add a regression test under `tests/student/` for one of the
affected queries, run `poe experiment` and then `poe verify`, commit both retained reports, and open
your pull request.

## Operational limits

This local system does not authenticate users, terminate TLS, or manage production secrets.
A retrieval request states its own tenancy and clearance, so that context is an asserted
identity rather than a verified one. The Compose PostgreSQL password and the LocalStack access keys
are local-only non-secret credentials. Never place real credentials, personal data, or production
records in this repository, including in `infra/corpus/`.

The measurements here make no production claim either. Latency is measured from one host against
one containerized database with no concurrent traffic, on a corpus of 18 documents, using a
deterministic hashed embedding rather than a trained one. The numbers are valid evidence about
*this* system and are not a benchmark of retrieval quality or of anything a production deployment
would see. The cached judge evidence is a recorded heuristic standing in for a model-based
evaluator, and says nothing about how a production judge would score these passages.

Named volumes preserve local PostgreSQL, Redis, Prometheus, Grafana, and Jaeger state across
`poe stop`. LocalStack object contents are deliberately not persisted; the initializer re-uploads
the supplied corpus artifacts on every start. The `poe reset` command deletes the named volumes.
This topology makes no backup, replication, high-availability, disaster-recovery, capacity,
latency-SLO, or availability claim.

See [JobQueue fidelity](docs/fidelity/JobQueue.md),
[ModelProvider fidelity](docs/fidelity/ModelProvider.md),
[ObjectStore fidelity](docs/fidelity/ObjectStore.md), and
[Retriever fidelity](docs/fidelity/Retriever.md) for the active adapter boundaries. The
[local runtime evidence](docs/fidelity/local-runtime.md) records the current measurement and its
qualification limits.
