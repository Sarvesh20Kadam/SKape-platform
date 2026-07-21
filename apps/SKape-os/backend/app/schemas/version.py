from pydantic import BaseModel


class VersionResponse(BaseModel):
    application: str
    version: str
    api: str