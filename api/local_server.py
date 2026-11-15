"""Local server (B3): same routes and contract as the Lambda, no AWS needed.

    python -m api.local_server            # http://127.0.0.1:8000, LLM_PROVIDER=mock, DATA_DIR=data
    make dev                              # same thing

Every request goes through `api.routes.dispatch`, exactly like `api/handler.py`,
so the local contract cannot drift from the deployed one.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402

from api.routes import ROUTES, dispatch  # noqa: E402

app = FastAPI(title="AlphaForge AI (local)", description="Simulation éducative, pas un conseil financier.",
              docs_url="/docs", redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type"],
    max_age=600,
)


async def _serve(request: Request) -> Response:
    body = (await request.body()).decode("utf-8", errors="replace") if request.method == "POST" else None
    resp = dispatch(request.method, request.url.path, dict(request.query_params), body)
    if resp.status == 204 or resp.body is None:
        return Response(status_code=resp.status)
    return JSONResponse(resp.body, status_code=resp.status, headers={"cache-control": "no-store"})


for (_method, _path), _ in ROUTES.items():
    app.add_api_route(_path, _serve, methods=[_method], include_in_schema=True, name=f"{_method} {_path}")


@app.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def _fallback(request: Request) -> Response:
    return await _serve(request)


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser(description="AlphaForge local API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    p.add_argument("--reload", action="store_true")
    a = p.parse_args()
    print(f"AlphaForge API locale: http://{a.host}:{a.port}  (LLM_PROVIDER={os.environ['LLM_PROVIDER']}, "
          f"DATA_DIR={os.environ['DATA_DIR']})")
    uvicorn.run("api.local_server:app", host=a.host, port=a.port, reload=a.reload)


if __name__ == "__main__":
    main()
