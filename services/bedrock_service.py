import os
from langchain_aws import ChatBedrock
from log_utils.logger import get_logger

logger = get_logger(__name__)

def get_bedrock_llm(temperature: float = 0):
    model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")
    region   = os.getenv("AWS_REGION", "us-east-1")
    logger.info("[bedrock_service] Using model=%s region=%s", model_id, region)
    return ChatBedrock(
        model_id=model_id,
        region_name=region,
        model_kwargs={"temperature": temperature},
    )
