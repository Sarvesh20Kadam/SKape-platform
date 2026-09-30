"""
SKape OS SQLAlchemy model registry.

Import all models here so SQLAlchemy can resolve
string-based relationships consistently.
"""

from app.models.user import User
from app.models.organization import Organization
from app.models.activity import Activity

from app.models.project import Project
from app.models.task import Task
from app.models.comment import Comment

from app.models.asset import Asset
from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.models.telemetry import DeviceTelemetry

from app.models.alert import Alert
from app.models.invitation import Invitation


__all__ = [
    "User",
    "Organization",
    "Activity",
    "Project",
    "Task",
    "Comment",
    "Asset",
    "Device",
    "DeviceCredential",
    "DeviceTelemetry",
    "Alert",
    "Invitation",
]