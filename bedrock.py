
import boto3

bedrock = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1"
)

response = bedrock.converse(
    modelId="amazon.nova-micro-v1:0",
    messages=[
        {
            "role": "user",
            "content": [
                {"text": "Explain what an ETF is in one sentence."}
            ]
        }
    ]
)

print(response["output"]["message"]["content"][0]["text"])
