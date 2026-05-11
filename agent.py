import os
from typing import Any

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import Runnable

from langchain_core.messages import SystemMessage

from config.models import get_bedrock_model, get_chat_bedrock_model
from prompts.system_prompts import AWS_INFRASTRUCTURE_PROMPT, REPOSITORY_ANALYSIS_PROMPT
from tools.aws_tools import AWS_TOOLS
from tools.repo_tools import REPO_TOOLS


# ---------------------------------------------------------------------------
# Strands Agent factory
# ---------------------------------------------------------------------------
def create_strands_agent(
    window_size: int = 10,
    region: str | None = None
) -> Agent:
    """
    Assemble and return the AWS Infrastructure Agent using Strands framework.

    Parameters
    ----------
    window_size : int
        Number of conversation turns kept in context. Default 10.
    region : str, optional
        AWS region override. Falls back to AWS_REGION env var.

    Returns
    -------
    strands.Agent
    """
    aws_region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

    model = get_bedrock_model(region=aws_region)
    print(f"[Strands Agent] Using Claude Haiku 4.5 via Amazon Bedrock")

    conversation_manager = SlidingWindowConversationManager(window_size=window_size)

    agent = Agent(
        model=model,
        system_prompt=AWS_INFRASTRUCTURE_PROMPT,
        tools=AWS_TOOLS,
        conversation_manager=conversation_manager
    )

    return agent

# ---------------------------------------------------------------------------
# LangGraph ReAct Agent factory
# ---------------------------------------------------------------------------
def create_langchain_agent(
    *,
    max_iterations: int = 15,
    region: str | None = None,
    streaming: bool = True
) -> Runnable:
    """
    Create a Repository Analysis Agent using LangGraph.

    This uses LangGraph's create_react_agent which provides a ReAct
    (Reasoning + Acting) loop with automatic tool calling.

    The agent uses:
    - ChatBedrock (LangChain) for model access
    - LangGraph ReAct agent pattern
    - Automatic think-act-observe loop
    - Repository analysis tools

    Parameters
    ----------
    max_iterations : int
        Maximum number of agent loop iterations. Default 15.
    region : str, optional
        AWS region override. Falls back to AWS_REGION env var.
    streaming : bool
        Enable streaming responses from the model.

    Returns
    -------
    Runnable
        Configured LangGraph agent ready to analyze repositories.
    """
    aws_region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

    model = get_chat_bedrock_model(region=aws_region, streaming=streaming)
    print(f"[LangChain Agent] Using Claude Haiku 4.5 via Amazon Bedrock")

    agent = create_react_agent(
        model,
        REPO_TOOLS,
        prompt=REPOSITORY_ANALYSIS_PROMPT,
    )
    
    return agent