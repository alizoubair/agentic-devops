import os

from agent import create_agent

try:
    from bedrock_agentcore import BedrockAgentCoreApp
    _AGENTCORE = True
except ImportError:
    _AGENTCORE = False
    print("bedrock-agentcore not installed — running plain HTTP fallback.")
    print("Install: pip install bedrock-agentcore bedrock-agentcore-starter-toolkit")


# ---------------------------------------------------------------------------
# Shared agent instance (created once at startup, reused across requests)
# ---------------------------------------------------------------------------
print("\n Initialising AWS Infrastructure Agent...")
_agent = create_agent()
print("Agent ready.\n")

# ---------------------------------------------------------------------------
# AgentCore entrypoint
# ---------------------------------------------------------------------------
if _AGENTCORE:
    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload: dict) -> dict:
        """
        AgentCore entrypoint — called for every POST /invocations request.

        AgentCore deserialises the JSON body, calls this function, and
        serialises the return value back to JSON.
        """
        return _handle(payload)


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------
def _handle(payload: dict) -> dict:
    """
    Process an incoming agent request.
    """
    prompt = payload.get("prompt", "").strip()
    if not prompt:
        return {"error": "Missing required field: 'prompt'"}
    
    region = payload.get("region")
    if region:
        os.environ["AWS_REGION"] = region
    
    response = _agent(prompt)

    return {
        "result": str(response),
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "model": "claude-haiku-4.5-bedrock"  # Updated to reflect Claude Haiku 4.5
    }
    
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _AGENTCORE:
        print("Starting via Bedrock AgentCore Runtime...")
        app.run()