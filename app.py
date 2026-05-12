import os

from agent import create_aws_infrastructure_agent, create_repository_analysis_agent, create_cdk_infrastructure_generation_agent

try:
    from bedrock_agentcore import BedrockAgentCoreApp
    _AGENTCORE = True
except ImportError:
    _AGENTCORE = False
    print("bedrock-agentcore not installed — running plain HTTP fallback.")
    print("Install: pip install bedrock-agentcore bedrock-agentcore-starter-toolkit")


# ---------------------------------------------------------------------------
# Shared agent instances (created once at startup, reused across requests)
# ---------------------------------------------------------------------------
print("\n Initialising AWS Infrastructure Agent (Strands)...")
_aws_agent = create_aws_infrastructure_agent()
print("AWS Infrastructure Agent ready.")

print("\n Initialising Repository Analysis Agent (LangChain)...")
_repo_agent = create_repository_analysis_agent()
print(" Repository Analysis Agent ready.")

print("\n Initialising CDK Infrastructure Generation Agent (LangChain)...")
_cdk_agent = create_cdk_infrastructure_generation_agent()
print(" CDK Infrastructure Generation Agent ready.")
print("Agent initialization complete.\n")


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
    Process an incoming agent request with support for multiple agents.
    
    Supports three agents:
    - AWS Infrastructure Agent (Strands-based): For observing AWS infrastructure
    - Repository Analysis Agent (LangChain-based): For analyzing code repositories
    - CDK Infrastructure Generation Agent (LangChain-based): For generating CDK code
    """
    prompt = payload.get("prompt", "").strip()
    if not prompt:
        return {"error": "Missing required field: 'prompt'"}
    
    # Agent selection - defaults to AWS Infrastructure Agent
    agent_type = payload.get("agent_type", "aws").lower()
    
    region = payload.get("region")
    if region:
        os.environ["AWS_REGION"] = region
    
    # Route to appropriate agent
    if agent_type == "aws" or agent_type == "infrastructure":
        if _aws_agent is None:
            return {"error": "AWS Infrastructure Agent not available"}
        response = _aws_agent(prompt)
        model_info = "claude-haiku-4.5-bedrock-strands"
        
    elif agent_type == "repo" or agent_type == "repository":
        if _repo_agent is None:
            return {"error": "Repository Analysis Agent not yet implemented"}
        
        # LangGraph agents expect messages format
        # Use stream to see intermediate tool calls
        steps = []
        final_response = ""
        
        try:
            for chunk in _repo_agent.stream({"messages": [("user", prompt)]}):
                # Collect all steps for visibility
                if "agent" in chunk:
                    agent_message = chunk["agent"]["messages"][0]
                    if hasattr(agent_message, 'tool_calls') and agent_message.tool_calls:
                        for tool_call in agent_message.tool_calls:
                            steps.append(f"Tool: {tool_call['name']}")
                
                if "tools" in chunk:
                    tool_message = chunk["tools"]["messages"][0]
                    steps.append(f"Tool Result: {tool_message.name}")
                
                # Get the final response
                if "agent" in chunk and chunk["agent"]["messages"]:
                    final_message = chunk["agent"]["messages"][-1]
                    if hasattr(final_message, 'content') and final_message.content:
                        final_response = final_message.content
        
        except Exception as e:
            # Fallback to simple invoke if streaming fails
            result = _repo_agent.invoke({"messages": [("user", prompt)]})
            final_response = result["messages"][-1].content if result.get("messages") else str(result)
            steps = ["Streaming unavailable, used simple invoke"]
        
        # Combine tool usage info with final response
        if steps:
            tool_info = "\n".join(steps)
            response = f"Tool Usage:\n{tool_info}\n\nAnalysis:\n{final_response}"
        else:
            response = final_response
            
        model_info = "claude-haiku-4.5-bedrock-langchain"
        
    elif agent_type == "cdk" or agent_type == "infrastructure-generation":
        if _cdk_agent is None:
            return {"error": "CDK Infrastructure Generation Agent not available"}
        
        # LangGraph agents expect messages format
        # Use stream to see intermediate tool calls
        steps = []
        final_response = ""
        
        try:
            for chunk in _cdk_agent.stream({"messages": [("user", prompt)]}):
                # Collect all steps for visibility
                if "agent" in chunk:
                    agent_message = chunk["agent"]["messages"][0]
                    if hasattr(agent_message, 'tool_calls') and agent_message.tool_calls:
                        for tool_call in agent_message.tool_calls:
                            steps.append(f"Tool: {tool_call['name']}")
                
                if "tools" in chunk:
                    tool_message = chunk["tools"]["messages"][0]
                    steps.append(f"Tool Result: {tool_message.name}")
                
                # Get the final response
                if "agent" in chunk and chunk["agent"]["messages"]:
                    final_message = chunk["agent"]["messages"][-1]
                    if hasattr(final_message, 'content') and final_message.content:
                        final_response = final_message.content
        
        except Exception as e:
            # Fallback to simple invoke if streaming fails
            result = _cdk_agent.invoke({"messages": [("user", prompt)]})
            final_response = result["messages"][-1].content if result.get("messages") else str(result)
            steps = ["Streaming unavailable, used simple invoke"]
        
        # Combine tool usage info with final response
        if steps:
            tool_info = "\n".join(steps)
            response = f"Tool Usage:\n{tool_info}\n\nAnalysis:\n{final_response}"
        else:
            response = final_response
            
        model_info = "claude-haiku-4.5-bedrock-langchain"
        
    else:
        return {"error": f"Unknown agent_type: '{agent_type}'. Use 'aws', 'repo', or 'cdk'"}

    return {
        "result": str(response),
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "model": model_info,
        "agent_type": agent_type
    }
    
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _AGENTCORE:
        print("Starting via Bedrock AgentCore Runtime...")
        app.run()