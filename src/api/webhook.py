"""
FastAPI webhook entry point for receiving alerts from Grafana/Alertmanager.

This module provides the HTTP API for:
- Receiving Alertmanager webhook notifications
- Accepting manual diagnostic requests
- Querying diagnosis status and results
"""

import asyncio
import logging
from datetime import datetime
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from ..agents import (
    create_orchestrator,
    DiagnosisResult,
    NetworkTroubleshootingOrchestrator,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for diagnosis results (use Redis/DB in production)
diagnosis_store: dict[str, DiagnosisResult] = {}
diagnosis_queue: asyncio.Queue = asyncio.Queue()

# Global orchestrator instance
orchestrator: NetworkTroubleshootingOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global orchestrator

    # Startup
    logger.info("Initializing network troubleshooting orchestrator...")
    orchestrator = create_orchestrator()
    logger.info("Orchestrator initialized successfully")

    # Start background worker
    worker_task = asyncio.create_task(diagnosis_worker())

    yield

    # Shutdown
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("Orchestrator shutdown complete")


app = FastAPI(
    title="NetSherlock",
    description="AI-driven network troubleshooting agent webhook API",
    version="0.1.0",
    lifespan=lifespan,
)


# Request/Response Models

class AlertmanagerAlert(BaseModel):
    """Single alert from Alertmanager."""

    status: str = "firing"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    endsAt: str | None = None
    generatorURL: str | None = None
    fingerprint: str | None = None


class AlertmanagerWebhook(BaseModel):
    """Alertmanager webhook payload."""

    version: str = "4"
    groupKey: str | None = None
    truncatedAlerts: int = 0
    status: str = "firing"
    receiver: str = ""
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str | None = None
    alerts: list[AlertmanagerAlert] = Field(default_factory=list)


class DiagnosticRequest(BaseModel):
    """Manual diagnostic request."""

    problem_type: str = Field(..., description="Type of problem: vm_network_latency, system_network_latency, etc.")
    src_node: str = Field(..., description="Source node IP address")
    dst_node: str | None = Field(None, description="Destination node IP address")
    vm_name: str | None = Field(None, description="VM name if applicable")
    description: str | None = Field(None, description="Additional problem description")


class DiagnosisResponse(BaseModel):
    """Diagnosis response."""

    diagnosis_id: str
    status: str  # "queued", "processing", "completed", "error"
    timestamp: str
    summary: str | None = None
    root_cause: dict[str, Any] | None = None
    recommendations: list[dict[str, Any]] | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    queue_size: int


# Background worker

async def diagnosis_worker():
    """Background worker that processes diagnosis requests."""
    logger.info("Diagnosis worker started")

    while True:
        try:
            # Wait for diagnosis request
            request_type, request_id, request_data = await diagnosis_queue.get()

            logger.info(f"Processing diagnosis request: {request_id}")

            if orchestrator is None:
                logger.error("Orchestrator not initialized")
                continue

            try:
                if request_type == "alert":
                    result = await orchestrator.diagnose_alert(request_data)
                else:
                    result = await orchestrator.diagnose_request(request_data)

                # Store result
                diagnosis_store[request_id] = result
                logger.info(f"Diagnosis completed: {request_id}")

            except Exception as e:
                logger.exception(f"Diagnosis failed for {request_id}: {e}")
                # Store error result
                diagnosis_store[request_id] = DiagnosisResult(
                    diagnosis_id=request_id,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    alert_source=None,
                    summary=f"Diagnosis failed: {str(e)}",
                    root_cause=None,
                    recommendations=[],
                )

            diagnosis_queue.task_done()

        except asyncio.CancelledError:
            logger.info("Diagnosis worker cancelled")
            break
        except Exception as e:
            logger.exception(f"Worker error: {e}")
            await asyncio.sleep(1)


# API Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if orchestrator else "initializing",
        timestamp=datetime.utcnow().isoformat() + "Z",
        queue_size=diagnosis_queue.qsize(),
    )


@app.post("/webhook/alertmanager", response_model=list[DiagnosisResponse])
async def receive_alertmanager_webhook(payload: AlertmanagerWebhook):
    """Receive webhook from Alertmanager.

    This endpoint receives alert notifications from Alertmanager and
    queues them for diagnosis processing.
    """
    if payload.status != "firing":
        # Only process firing alerts
        return []

    responses = []

    for alert in payload.alerts:
        if alert.status != "firing":
            continue

        # Generate diagnosis ID
        diagnosis_id = f"diag-{alert.fingerprint[:8]}" if alert.fingerprint else f"diag-{datetime.utcnow().timestamp():.0f}"

        # Check if already processing
        if diagnosis_id in diagnosis_store:
            existing = diagnosis_store[diagnosis_id]
            responses.append(DiagnosisResponse(
                diagnosis_id=diagnosis_id,
                status="completed" if existing.root_cause else "processing",
                timestamp=existing.timestamp,
                summary=existing.summary,
                message="Diagnosis already exists",
            ))
            continue

        # Queue for processing
        alert_data = {
            "labels": alert.labels,
            "annotations": alert.annotations,
            "startsAt": alert.startsAt,
        }

        await diagnosis_queue.put(("alert", diagnosis_id, alert_data))

        responses.append(DiagnosisResponse(
            diagnosis_id=diagnosis_id,
            status="queued",
            timestamp=datetime.utcnow().isoformat() + "Z",
            message="Alert queued for diagnosis",
        ))

        logger.info(f"Alert queued: {diagnosis_id} - {alert.labels.get('alertname', 'unknown')}")

    return responses


@app.post("/diagnose", response_model=DiagnosisResponse)
async def create_diagnosis(request: DiagnosticRequest):
    """Create a manual diagnostic request.

    This endpoint allows manual triggering of network diagnostics
    without an alert.
    """
    diagnosis_id = f"diag-manual-{datetime.utcnow().timestamp():.0f}"

    # Queue for processing
    request_data = request.model_dump()
    await diagnosis_queue.put(("manual", diagnosis_id, request_data))

    logger.info(f"Manual diagnosis queued: {diagnosis_id} - {request.problem_type}")

    return DiagnosisResponse(
        diagnosis_id=diagnosis_id,
        status="queued",
        timestamp=datetime.utcnow().isoformat() + "Z",
        message="Diagnosis request queued",
    )


@app.get("/diagnose/{diagnosis_id}", response_model=DiagnosisResponse)
async def get_diagnosis(diagnosis_id: str):
    """Get the status/result of a diagnosis.

    Returns the current status and results (if completed) for a
    specific diagnosis ID.
    """
    if diagnosis_id not in diagnosis_store:
        # Check if in queue
        raise HTTPException(
            status_code=404,
            detail=f"Diagnosis {diagnosis_id} not found",
        )

    result = diagnosis_store[diagnosis_id]

    return DiagnosisResponse(
        diagnosis_id=result.diagnosis_id,
        status="completed" if result.root_cause and result.root_cause.confidence > 0 else "error",
        timestamp=result.timestamp,
        summary=result.summary,
        root_cause={
            "category": result.root_cause.category.value if result.root_cause else None,
            "component": result.root_cause.component if result.root_cause else None,
            "confidence": result.root_cause.confidence if result.root_cause else 0,
            "evidence": result.root_cause.evidence if result.root_cause else [],
        } if result.root_cause else None,
        recommendations=[
            {"priority": r.priority, "action": r.action, "command": r.command}
            for r in result.recommendations
        ] if result.recommendations else None,
    )


@app.get("/diagnoses", response_model=list[DiagnosisResponse])
async def list_diagnoses(limit: int = 50, offset: int = 0):
    """List recent diagnoses.

    Returns a list of recent diagnosis results, ordered by timestamp.
    """
    # Sort by timestamp descending
    sorted_diagnoses = sorted(
        diagnosis_store.values(),
        key=lambda d: d.timestamp,
        reverse=True,
    )

    # Apply pagination
    paginated = sorted_diagnoses[offset : offset + limit]

    return [
        DiagnosisResponse(
            diagnosis_id=d.diagnosis_id,
            status="completed" if d.root_cause and d.root_cause.confidence > 0 else "error",
            timestamp=d.timestamp,
            summary=d.summary,
        )
        for d in paginated
    ]


# CLI entry point for development
def main():
    """Run the webhook server."""
    import uvicorn

    uvicorn.run(
        "src.api.webhook:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
    )


if __name__ == "__main__":
    main()
