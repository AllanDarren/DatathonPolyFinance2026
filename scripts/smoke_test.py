"""Smoke test against a running API (local or AWS). Only the standard library + jsonschema.

    python scripts/smoke_test.py                       # http://127.0.0.1:8000 (make dev)
    python scripts/smoke_test.py --base-url https://xxxx.execute-api.us-east-1.amazonaws.com
    python scripts/smoke_test.py --deployed            # URL from .build/stack_outputs.json

Checks: health, questionnaire, personas, profile, portfolio/parse, feed for Robert
(with 20 % NVDA considered), events, and the error format. Every response is
validated against contracts/alphaforge.schema.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.routes import ApiError, validate  # noqa: E402


class Smoke:
    def __init__(self, base: str, origin: str | None) -> None:
        self.base, self.origin, self.failures = base.rstrip("/"), origin, 0

    def call(self, method: str, path: str, body: Any = None) -> tuple[int, Any, dict[str, str], int]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"content-type": "application/json",
                                              **({"origin": self.origin} if self.origin else {})})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=35) as r:
                status, raw, headers = r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            status, raw, headers = e.code, e.read(), dict(e.headers)
        ms = int((time.perf_counter() - t0) * 1000)
        return status, json.loads(raw) if raw else None, {k.lower(): v for k, v in headers.items()}, ms

    def check(self, label: str, ok: bool, detail: str = "") -> None:
        print(f"  {'OK  ' if ok else 'FAIL'} {label}{('  ' + detail) if detail else ''}")
        self.failures += 0 if ok else 1

    def expect(self, label: str, method: str, path: str, contract: str, body: Any = None,
               status: int = 200, many: bool = False) -> Any:
        try:
            code, payload, headers, ms = self.call(method, path, body)
        except (urllib.error.URLError, TimeoutError) as exc:
            self.check(label, False, f"injoignable: {exc}")
            return None
        detail = f"{code} en {ms} ms"
        ok = code == status
        if ok:
            try:
                for item in (payload if many else [payload]):
                    validate(contract, item)
            except ApiError as exc:
                ok, detail = False, f"{detail}, hors contrat {contract}: {exc.details}"
        elif isinstance(payload, dict) and "error" in payload:
            detail += f" {payload['error'].get('code')}: {payload['error'].get('message')}"
        if self.origin and ok:
            allowed = headers.get("access-control-allow-origin")
            if allowed not in (self.origin, "*"):
                ok, detail = False, f"{detail}, CORS absent pour {self.origin} (reçu: {allowed})"
        self.check(label, ok, detail)
        return payload if ok else None


def run(base: str, origin: str | None) -> int:
    s = Smoke(base, origin)
    print(f"Smoke test: {base}" + (f" (origin {origin})" if origin else ""))
    health = s.expect("GET /health", "GET", "/health", "Health")
    if health:
        print(f"       version={health['version']} llm_provider={health['llm_provider']}")
    code, q, _, ms = s.call("GET", "/questionnaire")
    s.check("GET /questionnaire", code == 200 and bool(q and q.get("questions")), f"{code} en {ms} ms")
    personas = s.expect("GET /personas", "GET", "/personas", "Persona", many=True) or []
    if q and q.get("questions"):
        answers = {x["id"]: x["options"][0]["id"] for x in q["questions"]}
        s.expect("POST /profile", "POST", "/profile", "Profile", {"answers": answers})
    robert = next((p for p in personas if p["id"] == "robert"), None)
    if robert:
        pf = s.expect("POST /portfolio/parse", "POST", "/portfolio/parse", "Portfolio",
                      {"csv": robert["sample_portfolio_csv"]})
        if pf:
            feed = s.expect("POST /feed (Robert, 20 % NVDA)", "POST", "/feed", "FeedResponse",
                            {"profile": robert["profile"], "portfolio": pf,
                             "consideration": {"ticker": "NVDA", "intended_weight": 0.20}})
            if feed:
                coh = feed["coherence"]
                tools = [t["tool"] for t in (coh.get("agent_trace") or [])]
                guardian = {i["explanation"]["guardian"]["status"] for i in feed["items"]}
                gen = {i["explanation"]["generated_by"] for i in feed["items"]}
                print(f"       items={len(feed['items'])} hidden={feed['hidden']['count']} verdict={coh['verdict']} "
                      f"tools={tools} guardian={sorted(guardian)} generated_by={sorted(gen)}")
                s.check("Robert + 20 % NVDA jugé en tension ou incohérent", coh["verdict"] in ("tension", "incoherent"))
    else:
        s.check("persona robert présent", False)
    s.expect("GET /events?tickers=NVDA,RY.TO", "GET", "/events?tickers=NVDA,RY.TO", "Event", many=True)
    s.expect("POST /portfolio/parse (CSV vide -> 400)", "POST", "/portfolio/parse", "ErrorResponse",
             {"csv": ""}, status=400)
    s.expect("POST /feed (corps invalide -> 400)", "POST", "/feed", "ErrorResponse", {"profile": {}}, status=400)
    print("RÉSULTAT: " + ("OK" if s.failures == 0 else f"{s.failures} échec(s)"))
    return 0 if s.failures == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--deployed", action="store_true", help="use ApiUrl/WebUrl from .build/stack_outputs.json")
    p.add_argument("--origin", help="send this Origin header and check the CORS answer")
    a = p.parse_args()
    base, origin = a.base_url, a.origin
    if a.deployed:
        out = json.loads((ROOT / ".build" / "stack_outputs.json").read_text(encoding="utf-8"))
        base, origin = out["ApiUrl"], origin or out["WebUrl"]
    return run(base, origin)


if __name__ == "__main__":
    sys.exit(main())
