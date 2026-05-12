# ---------------------------------------------------------------------------
# Repository Analysis Tools for LangChain Agent
# ---------------------------------------------------------------------------

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Dependency to AWS Service Mapping
# ---------------------------------------------------------------------------

DEPENDENCY_TO_AWS_SERVICE = {
    # Databases
    "pg": "RDS PostgreSQL", "postgres": "RDS PostgreSQL", "psycopg2": "RDS PostgreSQL",
    "mysql": "RDS MySQL", "mysql2": "RDS MySQL", "pymysql": "RDS MySQL",
    "mongodb": "DocumentDB", "pymongo": "DocumentDB",
    
    # Caching & Storage
    "redis": "ElastiCache Redis", "ioredis": "ElastiCache Redis",
    "aws-sdk": "S3", "boto3": "S3", "@aws-sdk/client-s3": "S3",
    
    # Queuing & Search
    "celery": "SQS", "pika": "Amazon MQ", "elasticsearch": "OpenSearch",
    
    # Web frameworks
    "express": "ECS/Lambda", "fastapi": "ECS/Lambda", "flask": "ECS/Lambda",
    "django": "ECS/Lambda", "gin": "ECS/Lambda", "spring-boot": "ECS/Lambda",
}

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _wrap(data: Any, tool_name: str) -> str:
    """Wrap tool output in consistent JSON envelope."""
    return json.dumps({
        "tool": tool_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }, indent=2, default=str)

def _is_dependency_file(filename: str) -> bool:
    """Check if file is a dependency manifest."""
    return filename in {
        "package.json", "requirements.txt", "go.mod", "pom.xml", 
        "Cargo.toml", "Gemfile", "build.gradle"
    }

def _is_config_file(filename: str) -> bool:
    """Check if file is a configuration file."""
    return filename in {"Dockerfile", "docker-compose.yml", "Makefile"} or filename.endswith(".tf")

# ---------------------------------------------------------------------------
# TOOL 1 — scan_repository_structure
# ---------------------------------------------------------------------------

@tool
def scan_repository_structure(repo_path: str) -> str:
    """
    Scan a git repository and return its file structure with dependency/config files.

    Use this as the first step when analyzing a new repository to understand
    the overall layout and identify key files for further analysis.

    Parameters
    ----------
    repo_path : str
        Absolute path to the git repository root directory.

    Returns
    -------
    str
        JSON with file tree, dependency files, config files, and statistics.
    """
    try:
        repo_path_obj = Path(repo_path).resolve()
        if not repo_path_obj.exists() or not (repo_path_obj / ".git").exists():
            return _wrap({"error": "Invalid repository path"}, "scan_repository_structure")

        files, dependency_files, config_files = [], [], []
        
        for root, dirs, filenames in os.walk(repo_path_obj):
            # Skip common build/cache directories
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}]
            
            for filename in filenames:
                rel_path = str(Path(root, filename).relative_to(repo_path_obj))
                files.append(rel_path)
                
                if _is_dependency_file(filename):
                    dependency_files.append(rel_path)
                if _is_config_file(filename):
                    config_files.append(rel_path)

        return _wrap({
            "total_files": len(files),
            "files": files[:50],  # Limit for context
            "dependency_files": dependency_files,
            "config_files": config_files,
        }, "scan_repository_structure")

    except Exception as exc:
        return _wrap({"error": str(exc)}, "scan_repository_structure")

# ---------------------------------------------------------------------------
# TOOL 2 — read_file_content
# ---------------------------------------------------------------------------

@tool
def read_file_content(repo_path: str, file_path: str) -> str:
    """
    Read the content of a specific file with security and size validation.
    
    Use this tool to examine dependency files, configuration files, or any
    other files identified during repository scanning.

    Parameters
    ----------
    repo_path : str
        Absolute path to the git repository root directory.
    file_path : str
        Relative path to the file within the repository.
        
    Returns
    -------
    str
        JSON with file content, path, and size information.
    """
    try:
        full_path = (Path(repo_path) / file_path).resolve()
        
        if not str(full_path).startswith(str(Path(repo_path).resolve())):
            return _wrap({"error": "File outside repository"}, "read_file_content")
        
        if not full_path.exists():
            return _wrap({"error": "File not found"}, "read_file_content")
            
        if full_path.stat().st_size > 50000:  # 50KB limit
            return _wrap({"error": "File too large"}, "read_file_content")
            
        content = full_path.read_text(encoding="utf-8", errors="ignore")
        return _wrap({"file_path": file_path, "content": content}, "read_file_content")

    except Exception as exc:
        return _wrap({"error": str(exc)}, "read_file_content")

# ---------------------------------------------------------------------------
# TOOL 3 — analyze_dependencies
# ---------------------------------------------------------------------------

@tool
def analyze_dependencies(repo_path: str, dependency_file: str) -> str:
    """
    Parse a dependency file and extract the list of dependencies with language/framework detection.

    Supports package.json (Node.js), requirements.txt (Python), go.mod (Go),
    and other common dependency formats. Automatically detects the programming
    language and web framework based on dependencies.

    Parameters
    ----------
    repo_path : str
        Absolute path to the git repository root directory.
    dependency_file : str
        Relative path to the dependency file (e.g., "package.json", "requirements.txt").

    Returns
    -------
    str
        JSON with parsed dependencies, detected language, and framework information.
    """
    # Read the file directly instead of calling the tool
    try:
        repo_path_obj = Path(repo_path).resolve()
        full_path = (repo_path_obj / dependency_file).resolve()
        
        # Security: ensure file is within repo
        if not str(full_path).startswith(str(repo_path_obj)):
            return _wrap({"error": "File path outside repository"}, "analyze_dependencies")
        
        if not full_path.exists():
            return _wrap({"error": f"File not found: {dependency_file}"}, "analyze_dependencies")
            
        if full_path.stat().st_size > 50000:  # 50KB limit
            return _wrap({"error": "File too large"}, "analyze_dependencies")
            
        content = full_path.read_text(encoding="utf-8", errors="ignore")
        
    except Exception as exc:
        return _wrap({"error": f"Failed to read file: {str(exc)}"}, "analyze_dependencies")
    dependencies, language, framework = [], "unknown", None
    
    try:
        if dependency_file.endswith("package.json"):
            language = "Node.js"
            pkg = json.loads(content)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            dependencies = list(deps.keys())
            framework = "Express" if "express" in deps else "React" if "react" in deps else None
            
        elif dependency_file.endswith("requirements.txt"):
            language = "Python"
            for line in content.split("\n"):
                if line.strip() and not line.startswith("#"):
                    dep = re.split(r"[=<>!]", line.strip())[0]
                    dependencies.append(dep)
            framework = next((f for f in ["fastapi", "flask", "django"] if f in dependencies), None)
            
        elif dependency_file.endswith("go.mod"):
            language = "Go"
            dependencies = [line.split()[0] for line in content.split("\n") 
                          if line.strip() and not line.startswith(("module", "go", "require"))]

        return _wrap({
            "language": language,
            "framework": framework,
            "dependencies": dependencies,
            "total_dependencies": len(dependencies),
        }, "analyze_dependencies")

    except Exception as exc:
        return _wrap({"error": str(exc)}, "analyze_dependencies")

# ---------------------------------------------------------------------------
# TOOL 4 — map_aws_services
# ---------------------------------------------------------------------------

@tool
def map_aws_services(dependencies_json: str) -> str:
    """
    Map application dependencies to required AWS services.

    Analyzes the dependency list and identifies which AWS services would be
    needed to run the application (RDS, ElastiCache, S3, etc.). Also adds
    compute and networking requirements based on detected frameworks.

    Parameters
    ----------
    dependencies_json : str
        JSON output from analyze_dependencies tool containing dependency information.

    Returns
    -------
    str
        JSON with AWS service requirements mapped from dependencies.
    """
    try:
        deps_data = json.loads(dependencies_json).get("data", {})
        if "error" in deps_data:
            return _wrap(deps_data, "map_aws_services")
        
        dependencies = deps_data.get("dependencies", [])
        language = deps_data.get("language", "unknown")
        framework = deps_data.get("framework")
        
        aws_services = set()
        matched_deps = []
        
        # Map dependencies to services
        for dep in dependencies:
            for key, service in DEPENDENCY_TO_AWS_SERVICE.items():
                if key in dep.lower():
                    aws_services.add(service)
                    matched_deps.append(dep)
        
        # Add compute for web frameworks
        if framework or language != "unknown":
            aws_services.add("ECS/Lambda")
        
        # Add networking for web services
        if framework:
            aws_services.update(["VPC", "Application Load Balancer"])
        
        return _wrap({
            "language": language,
            "framework": framework,
            "matched_dependencies": matched_deps,
            "aws_services": sorted(list(aws_services)),
            "total_services": len(aws_services),
        }, "map_aws_services")

    except Exception as exc:
        return _wrap({"error": str(exc)}, "map_aws_services")

# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

REPO_TOOLS = [
    scan_repository_structure,
    read_file_content,
    analyze_dependencies,
    map_aws_services
]