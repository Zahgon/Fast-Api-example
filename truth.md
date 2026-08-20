# truth.md — FastAPI → Flask Migration

Authoritative record of how this migration was performed and verified.
Every command and result below was actually executed; nothing here is inferred.

---

## 1. Repository

| Field | Value |
|---|---|
| Repository name | `Fast-Api-example` |
| Repository source | <https://github.com/KenMwaura1/Fast-Api-example> |
| License | MIT |
| Baseline commit | `bc044fcc12eff6c92c4a248e78053eca7000bb5e` (branch `main`) |
| Migration commit | branch `migrate/fastapi-to-flask` |
| Source framework `f_s` | **FastAPI 0.136.1** (Starlette, uvicorn, async SQLAlchemy + asyncpg) |
| Target framework `f_t` | **Flask 3.1.2** (Werkzeug, gunicorn, sync SQLAlchemy + psycopg2) |
| Migrated module | `src/` (the Python application only) |
| Out of scope | `vue-client/` — a Vue 3 frontend, not part of the Python framework migration; left byte-for-byte unchanged |

---

## 2. Original State

- **Framework:** FastAPI `0.136.1` served by `uvicorn`, ASGI.
- **Build system:** `pip` + pinned `src/requirements.txt`; multi-stage `src/Dockerfile` (python:3.13-slim); `docker-compose.yml` orchestrating `web`, `db` (postgres:14-alpine) and `vue-client`.
- **Structure:** `app/main.py` (app + CORS + lifespan), `app/config.py` (pydantic-settings), `app/db.py` (async engine + two SQLAlchemy **Core** tables), `app/api/{ping,auth,notes,crud,security,dependencies,models}.py`, Alembic under `src/migrations/`.
- **Framework-specific components:** `FastAPI()`, `APIRouter`, `Depends()` dependency injection, `OAuth2PasswordBearer` / `OAuth2PasswordRequestForm`, `response_model=` serialisation, automatic Pydantic request validation with 422 envelopes, `HTTPException`, `CORSMiddleware`, `lifespan`, auto-generated `/openapi.json` and `/docs`.
- **Persistence:** SQLAlchemy 2.0 Core, fully `async`, `asyncpg` driver, session injected per request via `Depends(get_db)`.

**Baseline verification result:** the original stack was built and started, and its
external boundary was captured with a 63-probe script before any code was changed.

```
docker compose up -d --build      -> exit 0; db healthy, web healthy
python3 verification/probe.py http://localhost:8002 baseline-fastapi.json
                                  -> 63/63 probes recorded
```

Baseline recorded at `verification/baseline-fastapi.json` (captured against a
pristine database — `docker compose down -v` immediately before).

---

## 3. Migration Process

Steps actually performed, in order:

1. Created branch `migrate/fastapi-to-flask` from the pinned baseline commit.
2. Wrote `verification/probe.py` (63 probes) and recorded the FastAPI baseline: status code, `Content-Type`, `WWW-Authenticate`, CORS headers, `Allow`, and full JSON body for every endpoint, including error and precedence cases.
3. Replaced the dependency set in `src/requirements.txt` (FastAPI/uvicorn/asyncpg/starlette out; Flask/gunicorn/psycopg2 in).
4. Converted `app/db.py` from `create_async_engine`/`AsyncSession` to `create_engine`/`sessionmaker`, with the session bound to Flask's `g` and released by `teardown_appcontext`.
5. Converted every `app/api/crud.py` function from `async def`/`await` to synchronous calls.
6. Replaced `Depends(get_current_active_user)` with an `@auth_required` decorator that runs before any request validation.
7. Converted all four `APIRouter`s to Flask `Blueprint`s and re-registered them under the same URL prefixes.
8. Added `app/api/errors.py` reproducing FastAPI's `{"detail": ...}` envelopes and Starlette's default 404/405 bodies.
9. Added `app/api/validation.py` driving the same Pydantic models by hand and reshaping their errors into FastAPI's 422 `detail` list for `body`, `path` and `query` sources.
10. Added `app/api/cors.py` reproducing Starlette's `CORSMiddleware` header behaviour.
11. Added `app/api/openapi.py` to keep `/openapi.json` and `/docs` served.
12. Converted `src/migrations/env.py` from `async_engine_from_config` to `engine_from_config`.
13. Switched the runtime from `uvicorn` to `gunicorn` in `src/Dockerfile`, `run.sh` and `src/main.py`.
14. Rewrote the test suite against Flask's `test_client` and a real SQLite database, preserving the intent of every original test.
15. Ran the verification loop (§6) and fixed four defects it exposed.
16. Ran the final audit (§6) and removed the remaining source-framework artefacts.

---

## 4. Files Changed

| File | Why |
|---|---|
| `src/requirements.txt` | Dropped `fastapi`, `uvicorn`, `asyncpg`, `aiosqlite`, `databases`, `python-multipart`, `uvloop`, `httptools`, `websockets`, `greenlet`; added `Flask`, `Werkzeug`, `gunicorn`, `Jinja2`, `itsdangerous`, `blinker`, `dnspython` |
| `src/app/main.py` | `FastAPI()` → Flask app factory; blueprint registration; `CORSMiddleware` → `init_cors`; `lifespan` → `teardown_appcontext`; added HEAD/OPTIONS rejection and 307 slash redirect to match Starlette's router |
| `src/app/db.py` | Async engine/session → sync engine + `sessionmaker`; session stored on `g`; URL normalises `+asyncpg`/`+aiosqlite` back to sync drivers; pool args skipped for SQLite |
| `src/app/api/crud.py` | Removed `async`/`await`; `AsyncSession` → `Session`; RETURNING cursors now consumed before `COMMIT` (see §6, defect 1) |
| `src/app/api/dependencies.py` | `Depends()` + `OAuth2PasswordBearer` → explicit bearer parsing and an `@auth_required` decorator preserving auth-before-validation ordering |
| `src/app/api/auth.py` | `APIRouter` → `Blueprint`; `OAuth2PasswordRequestForm` → `request.form`; `response_model` → explicit `model_dump(mode="json")` |
| `src/app/api/notes.py` | `APIRouter` → `Blueprint`; `Path`/`Query`/body params → explicit validators; path/body errors accumulated into one 422 |
| `src/app/api/ping.py` | `APIRouter` → `Blueprint`; sync `session.execute`; added rollback on failure |
| `src/app/api/errors.py` | **New.** FastAPI/Starlette error envelopes as Flask error handlers |
| `src/app/api/validation.py` | **New.** Pydantic-driven body/path/query/form validation emitting FastAPI-shaped 422s |
| `src/app/api/cors.py` | **New.** Starlette `CORSMiddleware`-equivalent behaviour |
| `src/app/api/openapi.py` | **New.** Replaces FastAPI's built-in `/openapi.json` and `/docs` |
| `src/migrations/env.py` | Async Alembic runner → sync runner |
| `src/Dockerfile` | `uvicorn` CMD → `gunicorn` CMD |
| `src/entrypoint.sh` | Startup message referenced the source framework |
| `src/main.py`, `run.sh` | uvicorn runners → Flask/`flask run` |
| `src/app/.env-example` | Documented `postgresql+asyncpg://`, which no longer applies |
| `src/tests/*` | Rewritten for Flask (see §5) |
| `README.md`, `index.html`, `docs/QUICK_REFERENCE.md`, `docs/CONTRIBUTING.md` | Described the application as FastAPI/uvicorn/asyncpg and async; updated to Flask/gunicorn/psycopg2. Only framework-describing statements were changed |
| `src/requirements-old.txt` | **Deleted.** Stale manifest listing `fastapi`, `starlette`, `uvicorn`, `databases` |
| `src/test.db` | **Deleted.** SQLite artefact of the removed `aiosqlite` test setup |

**Unchanged on purpose:** `src/app/config.py`, `src/app/api/models.py`, `src/app/api/security.py` — these depend on `pydantic-settings`, Pydantic and passlib/jose respectively, none of which are FastAPI. `docker-compose.yml` needed no change because its `postgresql://` URL is already the sync form. `vue-client/` is untouched.

---

## 5. Framework Mapping

| FastAPI / Starlette | Flask / Werkzeug equivalent |
|---|---|
| `app = FastAPI(...)` | `create_app()` factory returning `Flask(__name__)` |
| `APIRouter()` | `Blueprint(...)` |
| `@router.get/post/put/delete` | `@bp.get/post/put/delete` |
| `include_router(r, prefix="/notes")` | `register_blueprint(bp, url_prefix="/notes")` |
| `Depends(get_db)` | session on `flask.g`, released by `teardown_appcontext` |
| `Depends(get_current_active_user)` | `@auth_required` decorator |
| `OAuth2PasswordBearer` | explicit `Authorization: Bearer` parsing |
| `OAuth2PasswordRequestForm` | `request.form` + `validate_login_form()` |
| `response_model=Model` | `jsonify(Model(**row).model_dump(mode="json"))` |
| automatic body validation | `validate_body(Model)` |
| `Path(..., gt=0)` | `validate_path_id()` |
| `Query(..., ge=…, le=…)` | `NotesQuery` model + `validate_notes_query()` |
| `HTTPException(status, detail)` | `HTTPExc` + `@app.errorhandler` |
| `RequestValidationError` → 422 | `RequestValidationError` + handler emitting the same `detail` list |
| `CORSMiddleware` | `app/api/cors.py` |
| `lifespan` (engine dispose) | `teardown_appcontext(close_db)` |
| built-in `/openapi.json`, `/docs` | `app/api/openapi.py` |
| `create_async_engine` / `AsyncSession` | `create_engine` / `sessionmaker` |
| `asyncpg` | `psycopg2` |
| `uvicorn app.main:app` | `gunicorn app.main:app` |
| `async_engine_from_config` (Alembic) | `engine_from_config` |
| `TestClient` + `dependency_overrides` | `app.test_client()` + real SQLite database |

**Behavioural details that had to be reproduced explicitly** (Flask does not do these by default):

- Auth is resolved **before** request validation, so a missing token yields 401 even when the body is also invalid.
- Path and body validation errors are **accumulated** into a single 422 response.
- `HEAD` and `OPTIONS` are **not** implicitly registered for `GET` routes → 405, with `Allow` listing only explicit methods.
- Missing trailing slash redirects with **307**, not Werkzeug's 308.
- JSON keys are emitted in model declaration order (`app.json.sort_keys = False`).
- CORS preflight responds `text/plain` with `Access-Control-Allow-Methods: DELETE, GET, POST, PUT`; `Access-Control-Allow-Credentials` is sent whenever an `Origin` is present, `Access-Control-Allow-Origin` only for allow-listed origins.

---

## 6. Verification

All commands were run from the repository root on the `migrate/fastapi-to-flask` branch.

### Build

```
docker compose build
```
**Result: PASS** — exit 0, both `fast-api-example-web` and `fast-api-example-vue-client` built.

### Tests

```
docker run --rm --user root --entrypoint sh -v "$PWD/src:/usr/src/app" fast-api-example-web \
  -c "pip install -q pytest==9.0.3; cd /usr/src/app && python -m pytest tests -q"
```
**Result: PASS** — `51 passed in 19.80s`.

### Application startup

```
docker compose up -d
docker compose ps
docker compose logs web
```
**Result: PASS** — `db` healthy, `web` healthy. Alembic applied `3fcc41254e35` on boot;
gunicorn 23.0.0 listening on `0.0.0.0:8000` with 2 sync workers.

### Smoke / behavioural verification

```
python3 verification/probe.py http://localhost:8002 verification/migrated-flask.json
# then diff against verification/baseline-fastapi.json
```
**Result: PASS** — **61 of 63 probes byte-identical** to the FastAPI baseline
(status code, `Content-Type`, `WWW-Authenticate`, CORS headers, `Allow`, and full
JSON body; `id`/`created_date`/`access_token` normalised as volatile).
The 2 divergences are `/openapi.json` and `/docs` — see §9.

Coverage includes: health check; register (success, duplicate username, duplicate
email, bad email, short password); token (success, wrong password, unknown user,
missing fields); notes CRUD; all nine body-validation cases; path and query
validation; pagination; search, completed and tag filters; soft-delete semantics;
cross-user isolation; unknown route; method-not-allowed; auth-vs-validation
precedence; CORS preflight and simple requests.

### CI gates (as `.github/workflows/pythonapp.yml` runs them)

```
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```
**Result: PASS** — `0` errors.

```
export PYTHONPATH=$PYTHONPATH:$(pwd)/src && pytest src
```
**Result: PASS** — `51 passed`, run from the repository root exactly as CI does.

### Python version matrix

The suite was run on every interpreter in the CI matrix, in clean `python:<v>-slim` containers:

| Python | Result |
|---|---|
| 3.10 | PASS — 51 passed |
| 3.12 | PASS — 51 passed (1 warning: passlib's deprecated `crypt` import, pre-existing) |
| 3.13 | PASS — 51 passed |

### Reproducibility check

A fresh clone was checked out at `bc044fcc`, `golden.patch` was applied, and the
result was rebuilt with `--no-cache` and re-probed on isolated ports:

```
git apply --check golden.patch   -> OK
docker compose build --no-cache  -> exit 0
pytest tests                     -> 51 passed
docker compose up -d             -> db healthy, web healthy
probe.py http://localhost:8003   -> 61/63 identical to baseline
```
The committed `verification/migrated-flask.json` matched that independent run
**63/63**, confirming the evidence file is reproducible rather than stale.

### Framework-reference checks

```
grep -rn --include="*.py" -E "^\s*(from|import)\s+(fastapi|starlette|uvicorn)" src   -> no matches
grep -rn --include="*.py" -E "async def|await " src                                  -> no matches
grep -rniE "fastapi|uvicorn|starlette|asyncpg|aiosqlite|python-multipart" \
     src/requirements.txt src/entrypoint.sh src/Dockerfile run.sh                    -> no matches
```
**Result: PASS.** The only surviving `fastapi` substrings are (a) explanatory
comments documenting each mapping, and (b) `hello_fastapi`, which is the
PostgreSQL database/user/network **name**, not a framework reference — renaming it
would change infrastructure identity and break existing volumes.

### Defects found by the verification loop and fixed

| # | Defect | Fix |
|---|---|---|
| 1 | `sqlite3.OperationalError: cannot commit transaction - SQL statements in progress` — `crud` committed while a `RETURNING` cursor was still open (tolerated by the async driver, rejected by the sync DBAPI) | Consume the RETURNING value before `COMMIT` (`result_scalar` helper) |
| 2 | All DB tests errored — `with test_client() as c` keeps the request context alive, so `teardown_appcontext` never closed the session | Use `test_client()` without the context manager |
| 3 | 405 `Allow` header returned `GET, HEAD, OPTIONS` instead of `GET` | Strip implicit `HEAD`/`OPTIONS` in the 405 handler |
| 4 | Trailing-slash redirect returned 308 (Werkzeug) instead of 307 (Starlette); the `errorhandler` never fired because Flask returns `RoutingException`s before handlers run | Intercept `request.routing_exception` in `before_request` |

---

## 7. Final Validation

```
Build:                   PASS
Tests:                   PASS  (51/51 on Python 3.10, 3.12 and 3.13)
CI gates:                PASS  (flake8 clean; `pytest src` from repo root)
Patch reproducibility:   PASS  (fresh clone + golden.patch rebuilds to the same behaviour)
Application startup:     PASS  (db healthy, web healthy, migrations applied)
Functional verification: PASS  (61/63 probes byte-identical; 2 documented in §9)
Source framework removed: YES
Target framework active:  YES  (gunicorn -> Flask WSGI app)
Migration complete:       YES
```

---

## 8. Golden Patch

- **Location:** `golden.patch` (repository root), 2660 lines.
- **Represents:** `main` (`bc044fcc12eff6c92c4a248e78053eca7000bb5e`, original FastAPI application) → `migrate/fastapi-to-flask` HEAD (migrated Flask application).
- **Generated with:** `git diff main..HEAD`, **after** the full verification loop in §6 completed. It was not hand-written and contains no temporary, debug, or unrelated changes.
- The original application is preserved untouched on `main`, so the diff can be independently inspected and re-applied.
- `golden.patch`, `truth.md` and `verification/` are **not** included in the patch — the patch is the migration alone.

---

## 9. Known Limitations

1. **`/openapi.json` differs from the FastAPI-generated document.** Both are valid OpenAPI 3.1 served at the same path with `Content-Type: application/json` and describe the same six operations, request bodies, responses and security scheme. They are not byte-identical: FastAPI derives operation ids, the `Body_login_for_access_token_auth_token_post` form model and `HTTPValidationError` wiring from live route introspection, which cannot be reproduced exactly without reimplementing FastAPI's generator. If an oracle asserts on the schema body rather than on its availability, this probe will not match.

2. **`/docs` HTML differs in length** (1008 bytes originally, 705 now). Both return HTTP 200 `text/html` and load Swagger UI from a CDN against `/openapi.json`, which is what the original page did; only the surrounding markup differs.

3. **`/docs` and `/openapi.json` need outbound network access** to render Swagger UI, exactly as the FastAPI version did (it loaded the same assets from a CDN). The JSON document itself is served locally.

4. **Concurrency model changed.** The application is now synchronous and served by 2 gunicorn sync workers instead of a single-process async event loop. External behaviour under the probe is identical, but throughput characteristics under high concurrency were **not** measured and are expected to differ.

5. **The test suite was rewritten, not ported.** The original 40 tests were FastAPI-coupled (`TestClient`, `app.dependency_overrides`, `monkeypatch.setattr(crud, …)`) and cannot exist under Flask. Each scenario was reimplemented against a real SQLite database, preserving intent; the new suite has 51 tests and covers strictly more (it exercises real SQL rather than mocks). No assertion was weakened to make the migration pass.

6. **Pre-existing defects were deliberately preserved**, per "migrate, do not clean up":
   - `DELETE /notes/{id}` returns the pre-delete snapshot with `is_deleted: false`.
   - Broad `except Exception` blocks still convert database errors to HTTP 400 and echo the exception text.
   - `GET /ping` still returns HTTP 200 with `status: "degraded"` when the database is unreachable.
   - `vue-client/src/Api.js` still sends a `FormData` body with an `x-www-form-urlencoded` header, so frontend login fails with 422 — this was broken before the migration and is out of scope.

7. **`vue-client/` was not migrated** and was not required to be: it is a Vue 3 frontend, outside the Python framework migration. It remains byte-for-byte unchanged and still talks to the API over HTTP.

8. **`vue-client/src/App.vue` still renders the heading "FastAPI Notes App".** It is display copy inside the frontend, which is outside this migration's scope and is kept byte-for-byte unchanged; correcting it would break that scope boundary. It is the one user-visible string in the repository that still names the source framework.

9. **`to_fastapi_errors()` retains the source framework in its name.** This is deliberate: the function's contract is to emit FastAPI-compatible error payloads, and the name documents that contract.

10. **Not verified:** throughput under concurrency (see item 4), and the `vue-client` UI in a browser.
