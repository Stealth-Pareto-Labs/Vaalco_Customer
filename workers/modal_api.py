"""
modal_api.py — deploy the FastAPI backend on Modal as an always-warm ASGI app.
=============================================================================
Runs the same apps/api/main.py FastAPI application. min_containers=1 keeps one
instance warm so interactive chat requests don't pay a cold start.

Deploy:
    modal deploy workers/modal_api.py
The deploy prints the public URL for the `fastapi_app` web endpoint.
"""

import modal

app = modal.App("vaalco-api")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "fastapi[standard]>=0.115", "uvicorn>=0.30", "pydantic>=2.7",
        "psycopg[binary]>=3.2", "openpyxl>=3.1", "python-dotenv>=1.0",
    )
    .add_local_dir("core", remote_path="/root/core")
    .add_local_dir("apps/api", remote_path="/root/apps/api")
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("vaalco-secrets")],
    min_containers=1,   # keep one instance warm for low-latency chat
    timeout=120,
)
@modal.asgi_app()
def fastapi_app():
    import sys
    for p in ("/root/apps/api", "/root/core"):
        if p not in sys.path:
            sys.path.insert(0, p)
    from main import app as web   # apps/api/main.py
    return web
