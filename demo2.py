import requests

# List all collections (GET /collections)
response = requests.get(
  "https://54d71640-e1ad-4f93-aa14-85cfa740d7d3.us-west-1-0.aws.cloud.qdrant.io:6333/collections",
  headers={
    "api-key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.ABb-yhjR7f9oUbltT4RonnE1HE_D9TfF_Fpxdm-QdYw"
  },
)

print(response.json())