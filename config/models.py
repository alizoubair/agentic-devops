import os

from strands.models import BedrockModel

from langchain_aws import ChatBedrock


# Claude Haiku 4.5 - cheapest Claude model (using cross-region inference profile)
CLAUDE_HAIKU_4_5 = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# -------------------------------------------------------------------
# Creates a Strands BedrockModel instance for AWS Infrastructure Agent
# -------------------------------------------------------------------
def get_bedrock_model(
    region: str | None = None,
    model_id: str = CLAUDE_HAIKU_4_5,  # Default to Claude Haiku 4.5
    temperature: float = 0.1,
    max_tokens: int = 4096
) -> BedrockModel:
    """
    Return a Strands BedrockModel configured for Claude Haiku 4.5.
    
    Used by the AWS Infrastructure Agent (Strands-based) for observing
    and analyzing AWS infrastructure state.

    Parameters
    ----------
    region : str, optional
        AWS region. Falls back to AWS_REGION / AWS_DEFAULT_REGION env vars.
    model_id : str
        Bedrock model ID. Default uses cross-region inference profile.
    temperature : float
        Low temperature (0.1) = more deterministic responses for infrastructure analysis.
    max_tokens : int
        Max response tokens. 4096 is sufficient for infrastructure reports.

    Returns
    -------
    BedrockModel
        Configured Strands BedrockModel instance.
    """
    aws_region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    
    # Create Strands BedrockModel instance for infrastructure analysis
    return BedrockModel(
        model_id=model_id,
        region_name=aws_region,
        temperature=temperature,
        max_tokens=max_tokens,
    )

# ----------------------------------------------------------------------
# Creates a LangChain ChatBedrock instance for Repository Analysis Agent
# ----------------------------------------------------------------------
def get_chat_bedrock_model(
    region: str | None = None,
    model_id: str = CLAUDE_HAIKU_4_5,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    streaming: bool = False
) -> ChatBedrock:
    """
    Return a LangChain ChatBedrock model configured for Claude Haiku 4.5.

    Used by the Repository Analysis Agent (LangChain-based) for analyzing
    code repositories and mapping them to AWS infrastructure requirements.

    Parameters
    ----------
    region : str, optional
        AWS region. Falls back to AWS_REGION / AWS_DEFAULT_REGION env vars.
    model_id : str
        Bedrock model ID. Default uses cross-region inference profile.
    temperature : float
        Low temperature (0.1) = more deterministic — appropriate for analysis tasks.
    max_tokens : int
        Max response tokens. 4096 is sufficient for structured analysis.
    streaming : bool
        Enable streaming responses. Useful for long-running analysis.

    Returns
    -------
    ChatBedrock
        Configured LangChain ChatBedrock model instance.
    """
    aws_region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

    # LangChain ChatBedrock configuration
    return ChatBedrock(
        region=aws_region,
        model_id=model_id,
        model_kwargs={
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        streaming=streaming,
    )
