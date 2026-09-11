#!/usr/bin/env python3
"""Behavioural probe: captures the exact external boundary of the Notes API.
Run against the ORIGINAL (FastAPI) stack to record a baseline, then against the
MIGRATED (Flask) stack; the two JSON outputs must be identical except for
volatile fields (ids/timestamps/tokens), which are normalised here."""
import json, sys, urllib.request, urllib.parse, urllib.error, re

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
OUT = sys.argv[2] if len(sys.argv) > 2 else "baseline.json"

def call(method, path, body=None, headers=None, form=False):
    url = BASE + path
    h = dict(headers or {})
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw, status, hdrs = r.read().decode(), r.status, r.headers
    except urllib.error.HTTPError as e:
        raw, status, hdrs = e.read().decode(), e.code, e.headers
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"__raw_len__": len(raw), "__is_html__": raw.lstrip().startswith("<")}
    return {
        "status": status,
        "content_type": hdrs.get("Content-Type", "").split(";")[0],
        "www_authenticate": hdrs.get("WWW-Authenticate"),
        "cors_allow_origin": hdrs.get("Access-Control-Allow-Origin"),
        "cors_allow_methods": hdrs.get("Access-Control-Allow-Methods"),
        "cors_allow_credentials": hdrs.get("Access-Control-Allow-Credentials"),
        "allow": hdrs.get("Allow"),
        "body": parsed,
    }

def norm(o):
    """Blank out volatile values so baseline/migrated can be compared."""
    if isinstance(o, dict):
        return {k: ("<VOLATILE>" if k in {"created_date", "access_token"} else norm(v))
                for k, v in o.items()}
    if isinstance(o, list):
        return [norm(x) for x in o]
    return o

R = {}
R["01_ping"] = call("GET", "/ping")
R["02_register"] = call("POST", "/auth/register",
    {"username": "probeuser", "email": "probe@example.com", "password": "password123"})
R["03_register_dup_username"] = call("POST", "/auth/register",
    {"username": "probeuser", "email": "other@example.com", "password": "password123"})
R["04_register_dup_email"] = call("POST", "/auth/register",
    {"username": "otheruser", "email": "probe@example.com", "password": "password123"})
R["05_register_bad_email"] = call("POST", "/auth/register",
    {"username": "baduser", "email": "not-an-email", "password": "password123"})
R["06_register_short_password"] = call("POST", "/auth/register",
    {"username": "baduser2", "email": "b2@example.com", "password": "short"})
R["07_token_ok"] = call("POST", "/auth/token",
    {"username": "probeuser", "password": "password123"}, form=True)
R["08_token_wrong_password"] = call("POST", "/auth/token",
    {"username": "probeuser", "password": "wrongpass"}, form=True)
R["09_token_unknown_user"] = call("POST", "/auth/token",
    {"username": "nobody", "password": "password123"}, form=True)

tok = ""
try:
    tok = json.loads(json.dumps(R["07_token_ok"]["body"])).get("access_token", "")
except Exception:
    pass
AUTH = {"Authorization": f"Bearer {tok}"}
BAD = {"Authorization": "Bearer not.a.real.token"}

R["10_notes_no_token"] = call("GET", "/notes/")
R["11_notes_bad_token"] = call("GET", "/notes/", headers=BAD)
R["12_notes_empty"] = call("GET", "/notes/", headers=AUTH)
R["13_create_note"] = call("POST", "/notes/",
    {"title": "probe note", "description": "probe description", "completed": False,
     "tags": ["alpha", "beta"]}, headers=AUTH)
R["14_create_note_minimal"] = call("POST", "/notes/",
    {"title": "second note", "description": "second description"}, headers=AUTH)
R["15_create_missing_fields"] = call("POST", "/notes/", {}, headers=AUTH)
R["16_create_title_too_short"] = call("POST", "/notes/",
    {"title": "x", "description": "valid description"}, headers=AUTH)
R["17_create_blank_title"] = call("POST", "/notes/",
    {"title": "   ", "description": "valid description"}, headers=AUTH)
R["18_create_title_too_long"] = call("POST", "/notes/",
    {"title": "x" * 256, "description": "valid description"}, headers=AUTH)
R["19_create_desc_too_long"] = call("POST", "/notes/",
    {"title": "valid title", "description": "x" * 1001}, headers=AUTH)
R["20_list_notes"] = call("GET", "/notes/", headers=AUTH)
R["21_get_note_1"] = call("GET", "/notes/1", headers=AUTH)
R["22_get_note_missing"] = call("GET", "/notes/999", headers=AUTH)
R["23_get_note_id_zero"] = call("GET", "/notes/0", headers=AUTH)
R["24_get_note_id_text"] = call("GET", "/notes/abc", headers=AUTH)
R["25_list_limit_over_max"] = call("GET", "/notes/?limit=101", headers=AUTH)
R["26_list_limit_zero"] = call("GET", "/notes/?limit=0", headers=AUTH)
R["27_list_negative_skip"] = call("GET", "/notes/?skip=-1", headers=AUTH)
R["28_list_pagination"] = call("GET", "/notes/?skip=0&limit=1", headers=AUTH)
R["29_list_search_hit"] = call("GET", "/notes/?search=probe", headers=AUTH)
R["30_list_search_miss"] = call("GET", "/notes/?search=zzzznomatch", headers=AUTH)
R["31_list_completed_false"] = call("GET", "/notes/?completed=false", headers=AUTH)
R["32_list_completed_true"] = call("GET", "/notes/?completed=true", headers=AUTH)
R["33_list_tag_hit"] = call("GET", "/notes/?tag=alpha", headers=AUTH)
R["34_list_tag_miss"] = call("GET", "/notes/?tag=nosuchtag", headers=AUTH)
R["35_update_note"] = call("PUT", "/notes/1",
    {"title": "updated title", "description": "updated description",
     "completed": True, "tags": ["gamma"]}, headers=AUTH)
R["36_get_after_update"] = call("GET", "/notes/1", headers=AUTH)
R["37_update_missing"] = call("PUT", "/notes/999",
    {"title": "nope title", "description": "nope description"}, headers=AUTH)
R["38_update_invalid_body"] = call("PUT", "/notes/1", {"title": "x"}, headers=AUTH)
R["39_delete_note"] = call("DELETE", "/notes/1", headers=AUTH)
R["40_get_after_delete"] = call("GET", "/notes/1", headers=AUTH)
R["41_delete_again"] = call("DELETE", "/notes/1", headers=AUTH)
R["42_list_after_delete"] = call("GET", "/notes/", headers=AUTH)
R["43_openapi"] = call("GET", "/openapi.json")
R["44_docs"] = call("GET", "/docs")
R["45_unknown_route"] = call("GET", "/no-such-route")
R["46_method_not_allowed"] = call("DELETE", "/ping")

# second user must not see first user's notes
R["47_register_user2"] = call("POST", "/auth/register",
    {"username": "probeuser2", "email": "probe2@example.com", "password": "password123"})
t2 = call("POST", "/auth/token", {"username": "probeuser2", "password": "password123"}, form=True)
tok2 = t2["body"].get("access_token", "") if isinstance(t2["body"], dict) else ""
R["48_user2_sees_no_notes"] = call("GET", "/notes/", headers={"Authorization": f"Bearer {tok2}"})
R["49_user2_cannot_read_user1_note"] = call("GET", "/notes/2", headers={"Authorization": f"Bearer {tok2}"})


# --- precedence probes: does auth run before request validation? ---
R["50_no_token_bad_body"] = call("POST", "/notes/", {"title": "x"})
R["51_no_token_bad_path"] = call("GET", "/notes/0")
R["52_no_token_bad_query"] = call("GET", "/notes/?limit=101")
R["53_bad_token_bad_body"] = call("POST", "/notes/", {"title": "x"}, headers=BAD)
R["54_auth_bad_path_valid_token"] = call("GET", "/notes/-5", headers=AUTH)
R["55_register_missing_all"] = call("POST", "/auth/register", {})
R["56_token_missing_fields"] = call("POST", "/auth/token", {}, form=True)
R["57_create_note_extra_field"] = call("POST", "/notes/",
    {"title": "extra field", "description": "has unknown key", "bogus": 1}, headers=AUTH)
R["58_ping_head"] = call("HEAD", "/ping")
R["59_notes_trailing_slash_omitted"] = call("GET", "/notes", headers=AUTH)


R["60_options_ping"] = call("OPTIONS", "/ping")
R["61_cors_preflight"] = call("OPTIONS", "/notes/", headers={
    "Origin": "http://localhost:5173",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "authorization,content-type"})
R["62_cors_simple_get"] = call("GET", "/ping", headers={"Origin": "http://localhost:5173"})
R["63_cors_disallowed_origin"] = call("GET", "/ping", headers={"Origin": "http://evil.test"})

with open(OUT, "w") as f:
    json.dump(norm(R), f, indent=2, sort_keys=True)
print(f"wrote {OUT}: {len(R)} probes")
for k in sorted(R):
    print(f"  {k:35s} {R[k]['status']}")
