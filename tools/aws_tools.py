import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from strands import tool

def _region() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

def _client(service: str, region: str | None = None) -> Any:
    try:
        return boto3.client(service, region_name=region or _region())
    except NoCredentialsError:
        raise RuntimeError(
            "AWS credentials not found.\n"
            "Configure with: aws configure"
        )

def _wrap(data: Any, tool_name: str) -> str:
    """
    Wrap tool output in a consistent JSON envelope.

    The agent reads tool output as text in its context window.
    Consistent structure + ISO timestamps help the model parse
    and cite results accurately.
    """
    return json.dumps(
        {
            "tool": tool_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "region": _region(),
            "data": data,
        },
        indent=2,
        default=str
    )

# ---------------------------------------------------------------------------
# TOOL 1 — list_aws_resources
# ---------------------------------------------------------------------------

@tool
def list_aws_resources(service_type: str, region: str = "us-east-1") -> str:
    """
    List running AWS resources of the specified type in a region.

    Use this tool whenever you need to know what is currently deployed.
    Never guess or rely on prior knowledge — always call this tool first.

    Parameters
    ----------
    service_type : str
        One of: "ecs", "ec2", "rds", "lambda"
    region : str
        AWS region to query. Default: "us-east-1"

    Returns
    -------
    str
        JSON list of resources with status information.
    """

    try:
        if service_type.lower().strip() == "ecs":
            return _live_list_ecs(region)
        else:
            return _wrap({"error": f"Unsupported service_type: '{service_type}"}, "describe_resource")
    except ClientError as exc:
        return _wrap({"error": str(exc)}, "list_aws_resources")

def _live_list_ecs(region: str) -> str:
    """List all ECS services across all clusters in the region."""
    ecs = _client("ecs", region)
    resources = []
    
    cluster_arns = ecs.list_clusters().get("clusterArns", [])
    
    for arn in cluster_arns:
        cluster = arn.split("/")[-1]  # Extract cluster name from ARN
        
        for svc_arn in ecs.list_services(cluster=arn).get("serviceArns", []):
            for svc in ecs.describe_services(cluster=arn, services=[svc_arn]).get("services", []):
                resources.append({
                    "name": svc["serviceName"], 
                    "cluster": cluster,
                    "status": svc["status"],
                    "running": svc["runningCount"], 
                    "desired": svc["desiredCount"],
                    "task_def": svc["taskDefinition"].split("/")[-1],  # Extract task def name
                })
    
    return _wrap({"service_type": "ecs", "region": region, "count": len(resources), "resources": resources}, "list_aws_resources")

# ---------------------------------------------------------------------------
# TOOL 2 — describe_resource
# ---------------------------------------------------------------------------

@tool
def describe_resource(service_type: str, resource_name: str, region: str = "us-east-1") -> str:
    """
    Get detailed configuration and recent events for a specific AWS resource.

    Use this after list_aws_resources identifies something worth investigating.
    Provides much more detail than the listing — including recent events,
    deployment history, and configuration parameters.

    Parameters
    ----------
    service_type : str
        One of: "ecs", "ec2", "rds"
    resource_name : str
        Service name (ECS), instance ID (EC2), or DB identifier (RDS).
    region : str
        AWS region. Default: "us-east-1"

    Returns
    -------
    str
        JSON with full resource details, recent events, and configuration.
    """
    try:
        if service_type.lower() == "ecs":
            return _live_describe_ecs(resource_name, region)
        else:
            return _wrap({"error": f"Unsupported service_type: '{service_type}'"}, "describe_resource")
    except ClientError as exc:
        return _wrap({"error": str(exc)}, "describe_resource")

def _live_describe_ecs(service_name: str, region: str) -> str:
    """Get detailed information about a specific ECS service."""
    ecs = _client("ecs", region)
    
    cluster_arns = ecs.list_clusters().get("clusterArns", [])
    for arn in cluster_arns:
        cluster = arn.split("/")[-1]
        try:
            services = ecs.describe_services(cluster=arn, services=[service_name]).get("services", [])
            if services:
                svc = services[0]
                result = {
                    "name": svc["serviceName"],
                    "cluster": cluster,
                    "status": svc["status"],
                    "running": svc["runningCount"],
                    "desired": svc["desiredCount"],
                    "task_def": svc["taskDefinition"].split("/")[-1],
                    "events": [e["message"] for e in svc.get("events", [])[:3]]
                }
                return _wrap(result, "describe_services")
        except ClientError:
            continue
    
    return _wrap({"error": f"ECS Service '{service_name}' not found"}, "describe_services")

# ---------------------------------------------------------------------------
# TOOL 3 — check_resource_health
# ---------------------------------------------------------------------------
@tool
def check_resource_health(service_type: str, resource_name: str, region: str = "us-east-1") -> str:
    """
    Evaluate the health of a specific AWS resource and return a structured
    health report with findings and recommended actions.

    This tool synthesises raw AWS data into an opinionated assessment:
      - healthy  : resource is operating normally
      - degraded : resource is running but has issues
      - critical : resource is down or severely impaired

    Use this when you need to give a definitive health verdict rather than
    just listing raw state. Recommended next step: request_human_review if
    the status is degraded or critical.

    Parameters
    ----------
    service_type : str
        One of: "ecs", "ec2", "rds"
    resource_name : str
        Name or ID of the resource.
    region : str
        AWS region. Default: "us-east-1"

    Returns
    -------
    str
        JSON health report: status, findings list, recommendations list.
    """
    raw = describe_services(service_type, resource_name, region)
    detail = json.loads(raw)["data"]
    if "error" in detail:
        return _wrap({"health": "unknown", "error": detail["error"]}, "check_resource_health")
    return _derive_health(service_type, resource_name, detail, region)

def _derive_health(service_type: str, name: str, detail: dict, region: str) -> str:
    findings: list[str] = []
    recommendations: list[str] = []
    health = "healthy"

    if svc == "ecs":
        running, desired = detail.get("running", 0), detail.get("desired", 0)
        if running < desired:
            health = "degraded" if running > 0 else "critical"
            findings.append(f"Running ({running}) < Desired ({desired})")
            recommendations.append("Check CloudWatch Logs for task failure details")
        else:
            findings.append(f"Running ({running}) == Desired ({desired})")
        for evt in detail.get("recent_events", [])[:3]:
            msg = evt.get("message", "")
            if any(w in msg.lower() for w in ("fail", "error", "stopped", "exit")):
                health = "degraded" if health == "healthy" else health
                findings.append(f"Event: {msg[:120]}")
    
    return _wrap(
        {"resource": name, "service_type": service_type, "region": region,
         "health": health, "findings": findings, "recommendations": recommendations},
         "check_resource_health",
    )

# ---------------------------------------------------------------------------
# Tool registry for AWS Infrastructure Agent (Strands-based)
# ---------------------------------------------------------------------------

AWS_TOOLS = [
    list_aws_resources,
    describe_resource,
    check_resource_health
]