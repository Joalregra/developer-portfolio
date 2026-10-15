from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    environment: str
    # Short hash of the knowledge files, so a deploy can be checked from the outside.
    knowledge_version: str
