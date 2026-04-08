from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.config import load_settings
from app.fs import load_json, load_yaml

settings = load_settings()
app = FastAPI(title="Aurora Control Plane API")


@app.get("/health")
def health() -> dict[str, object]:
    history = load_json(settings.lab_root / "artifacts" / "rollout_history.json", [])

    return {
        "status": "ok",
        "service": settings.service_name,
        "lab_ready": settings.lab_root.exists(),
        "rollouts": len(history),
    }


@app.get("/rollouts/last")
def get_last_rollout() -> dict[str, object]:
    report_path = settings.lab_root / "artifacts" / "last_rollout.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="No rollouts have been executed yet")
    return load_json(report_path)


@app.get("/deployments/{service}")
def get_deployment(service: str) -> dict[str, object]:
    if service != settings.service_name:
        raise HTTPException(status_code=404, detail="Unknown service")

    deployment_path = settings.lab_root / "cluster" / "live" / "deployments" / f"{service}.yaml"
    if not deployment_path.exists():
        raise HTTPException(status_code=404, detail="Deployment state is missing")

    return load_yaml(deployment_path)["deployment"]


@app.get("/routes/{service}")
def get_route(service: str) -> dict[str, object]:
    if service != settings.service_name:
        raise HTTPException(status_code=404, detail="Unknown service")

    route_path = settings.lab_root / "cluster" / "live" / "routes" / f"{service}.yaml"
    if not route_path.exists():
        raise HTTPException(status_code=404, detail="Route state is missing")

    return load_yaml(route_path)["route"]
