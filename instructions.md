# Task: Migrate this application from FastAPI to Flask

## What this repository is

A small REST API for managing notes, with user registration and JWT-based
authentication. The Python application lives entirely under `src/`:

```
src/
  app/
    main.py          application setup
    config.py        settings
    db.py            database engine + table definitions
    api/             routes, CRUD, models, security helpers
  migrations/        Alembic migrations
  tests/             test suite
  Dockerfile
  requirements.txt
```

The API exposes a health check, user registration, token login, and CRUD for
notes. It is packaged with Docker and orchestrated by `docker-compose.yml`
together with a PostgreSQL database and a Vue frontend.

## Your task

Convert the Python application in `src/` from **FastAPI** to **Flask**.

When you are done, the application must be a Flask application: FastAPI and its
server must no longer be used or installed, and Flask must be what actually
serves the API.

## Requirements

1. **Keep the external HTTP behaviour identical.**
   The migrated API must be indistinguishable from the original to any client.
   For every request the original could receive, the Flask version must return
   the same status code, the same response headers, and the same response body.
   This applies to successful requests *and* to every error case.

2. **Keep the same public surface.**
   Same URLs, same HTTP methods, same request formats, same authentication
   scheme. Do not add, remove, rename or re-shape any endpoint.

3. **Keep the persistence layer working.**
   The database schema must not change. Alembic migrations must still run.
   The application must keep working against PostgreSQL, using the same
   `DATABASE_URL` configuration.

4. **Keep the project runnable.**
   The Docker image, `docker-compose.yml`, the entrypoint and the helper run
   script must all still build and start the application. The CI workflow in
   `.github/workflows/pythonapp.yml` must still pass.

5. **Migrate — do not clean up.**
   Do not fix pre-existing bugs, do not refactor unrelated code, and do not
   change behaviour you were not asked to change. If the original had a quirk,
   the migration should keep it. Only change what the framework switch requires.

6. **Update the tests.**
   The existing test suite is written against FastAPI's test tooling and cannot
   run under Flask unchanged. Port it. Every scenario the original suite covered
   must still be covered, with equivalent assertions. Do not delete, skip, stub
   or weaken a test to make the suite go green.

7. **Update the documentation that describes the framework.**
   Files that state which framework, server or database driver this project uses
   should be corrected. Only change statements that are made untrue by the
   migration; leave everything else alone.

## Out of scope

- `vue-client/` — the Vue frontend is not part of this migration. Leave it
  byte-for-byte unchanged.
- Infrastructure identity (database names, users, network names, volumes) —
  renaming these would break existing deployments.

## How your work will be judged

Three checks must all pass:

1. **Test cases** — the ported test suite builds and runs green, with no
   dropped, skipped, stubbed or weakened cases.
2. **Behaviour tests** — the original and the migrated application are driven
   with the same requests and their responses are compared. Differences in
   status, headers or body count as failures.
3. **Coverage tests** — a coverage tool is run against the migrated
   application and must report at least **70%**.

Alongside these, the application must build, start, and serve traffic, and no
trace of the source framework may remain in the installed dependencies or in
the application's imports.

## Deliverable

The migrated application on a branch, plus a patch containing the migration
and nothing else — no debug code, no scratch files, no unrelated changes.
