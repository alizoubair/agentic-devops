import os
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager

from config.models import get_bedrock_model
from prompts import SYSTEM_PROMPT
from tools.aws_tools import ALL_TOOLS

# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------
def create_agent(
    window_size: int = 10,
    region: str | None = None
) -> Agent:
    """
    Assemble and return the Module 1 AWS Infrastructure Agent.

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
    print(f"[Agent] Using Claude Haiku 4.5 via Amazon Bedrock")

    conversation_manager = SlidingWindowConversationManager(window_size=window_size)

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
        conversation_manager=conversation_manager
    )

    return agent

