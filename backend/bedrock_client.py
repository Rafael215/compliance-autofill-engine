import os, json
import boto3
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID")

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

def call_llm(prompt: str) -> str:
    if not MODEL_ID:
        raise ValueError("BEDROCK_MODEL_ID is not set. Put it in your .env file.")

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.2
    }

    resp = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body)
    )
    data = json.loads(resp["body"].read())
    return data["content"][0]["text"]
