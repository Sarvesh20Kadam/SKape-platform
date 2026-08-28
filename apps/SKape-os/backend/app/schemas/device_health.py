from pydantic import BaseModel


class DeviceHealthResponse(BaseModel):
    status: str
    reason: str