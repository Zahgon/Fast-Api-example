#!/bin/bash
# Verify golden.patch for the FastAPI -> Flask migration.
# Usage:  ./verify_golden.sh [/path/to/Fast-Api-example]
set -u

REPO="${1:-$HOME/Desktop/FrameWork_Migration/Fast-Api-example}"
BASE="bc044fcc12eff6c92c4a248e78053eca7000bb5e"
PATCH="$REPO/golden.patch"
WORK="$(mktemp -d)"
PORT=8009
PROJ="goldenverify"
pass=0; fail=0
ok(){ echo "  PASS  $1"; pass=$((pass+1)); }
no(){ echo "  FAIL  $1"; fail=$((fail+1)); }

echo "== 1. Patch integrity =="
[ -s "$PATCH" ] && ok "golden.patch exists ($(wc -l < "$PATCH") lines)" || { no "golden.patch missing"; exit 1; }
echo "  sha256: $(shasum -a 256 "$PATCH" | cut -d' ' -f1)"
echo "  expect: 7bd76bb176b02e339e5f9a947080dd77dd11952fadfab12b959f49107b6e9810"

echo "== 2. Applies cleanly to the pinned base commit =="
git clone -q "$REPO" "$WORK/t" && cd "$WORK/t" && git checkout -q "$BASE"
grep -q "from fastapi import FastAPI" src/app/main.py && ok "base commit is the FastAPI original" || no "base commit unexpected"
git apply --check "$PATCH" 2>/dev/null && ok "git apply --check" || no "git apply --check"
git apply "$PATCH" 2>/dev/null && ok "patch applied" || { no "patch apply"; exit 1; }

echo "== 3. Source framework removed / target active =="
[ "$(grep -rn --include='*.py' -cE '^[[:space:]]*(from|import)[[:space:]]+(fastapi|starlette|uvicorn)' src | grep -v ':0$' | wc -l)" -eq 0 ] \
  && ok "no fastapi/starlette/uvicorn imports" || no "framework imports remain"
[ -z "$(grep -rn --include='*.py' -E 'async def|await ' src)" ] && ok "no async/await left" || no "async/await remains"
grep -q "^Flask==" src/requirements.txt && ok "Flask pinned in requirements" || no "Flask not pinned"
grep -q "gunicorn" src/Dockerfile && ok "Dockerfile runs gunicorn" || no "Dockerfile not gunicorn"

echo "== 4. Round-trip: patched tree == migration branch =="
if diff -r -x .git -x golden.patch -x truth.md -x verification -x __pycache__ \
     -x .pytest_cache -x node_modules . "$REPO" >/dev/null 2>&1; then
  ok "patched tree matches the migrated repo exactly"
else
  no "patched tree differs:"; diff -r -x .git -x golden.patch -x truth.md -x verification \
     -x __pycache__ -x .pytest_cache -x node_modules . "$REPO" | head -5
fi

echo "== 5. Build =="
docker compose -p "$PROJ" build web >/dev/null 2>&1 && ok "docker compose build" || no "build failed"

echo "== 6. Tests =="
T=$(docker run --rm --user root --entrypoint sh -v "$PWD/src:/usr/src/app" "${PROJ}-web" \
     -c "pip install -q pytest==9.0.3 >/dev/null 2>&1; cd /usr/src/app && python -m pytest tests -q 2>&1 | tail -1")
echo "  -> $T"; echo "$T" | grep -q "51 passed" && ok "51/51 tests" || no "tests"

echo "== 7. Deploy + behavioural parity =="
sed -i.bak "s/\"8002:8000\"/\"$PORT:8000\"/; s/\"5173:5173\"/\"5176:5173\"/" docker-compose.yml
docker compose -p "$PROJ" up -d >/dev/null 2>&1
for i in $(seq 1 40); do docker compose -p "$PROJ" ps --format '{{.Service}} {{.Status}}' 2>/dev/null | grep -q '^web.*healthy' && break; sleep 3; done
docker compose -p "$PROJ" ps --format '{{.Service}} {{.Status}}' | grep -q '^web.*healthy' && ok "web healthy" || no "web not healthy"
python3 "$REPO/verification/probe.py" "http://localhost:$PORT" "$WORK/probe.json" >/dev/null 2>&1
R=$(python3 -c "
import json;b=json.load(open('$REPO/verification/baseline-fastapi.json'));m=json.load(open('$WORK/probe.json'))
d=[k for k in sorted(b) if b[k]!=m.get(k)];print(f'{len(b)-len(d)}/{len(b)} identical; divergent={d}')")
echo "  -> $R"; echo "$R" | grep -q "^61/63" && ok "behavioural parity 61/63" || no "parity"

echo "== cleanup =="
docker compose -p "$PROJ" down -v >/dev/null 2>&1
docker rmi -f "${PROJ}-web" "${PROJ}-vue-client" >/dev/null 2>&1
cd / && rm -rf "$WORK"
echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" -eq 0 ] && echo "golden.patch VERIFIED" || echo "VERIFICATION FAILED"
