import os

from strands.models import BedrockModel

# Claude Haiku 4.5 - cheapest Claude model (using cross-region inference profile)
CLAUDE_HAIKU_4_5 = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

def get_bedrock_model(
    region: str | None = None,
    model_id: str = CLAUDE_HAIKU_4_5,  # Default to Claude Haiku 4.5 - cheap and capable
    temperature: float = 0.1,
    max_tokens: int = 4096
) -> BedrockModel:
    aws_region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    return BedrockModel(
        model_id=model_id,
        region_name=aws_region,
        temperature=temperature,
        max_tokens=max_tokens,
    )
