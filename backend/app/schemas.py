from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ConsentType, EventStatus, ProcessingStatus, Role


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str | None
    role: Role | None


class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class EventUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    event_code: str
    status: EventStatus
    created_at: datetime


class EventJoin(BaseModel):
    event_code: str = Field(min_length=8, max_length=12)


class RoleUpdate(BaseModel):
    role: Role


class PhotographerAssignmentCreate(BaseModel):
    photographer_id: str = Field(min_length=1, max_length=36)


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(pattern=r"^image/(jpeg|png|webp)$")
    checksum: str | None = Field(default=None, max_length=128)


class UploadResponse(BaseModel):
    photo_id: str
    storage_key: str
    upload_url: str
    expires_in: int


class SelfieUploadResponse(BaseModel):
    storage_key: str
    upload_url: str
    expires_in: int


class PhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    storage_key: str
    checksum: str | None
    processing_status: ProcessingStatus


class UploadedPhotoResponse(PhotoResponse):
    event_name: str
    photo_url: str


class ConsentCreate(BaseModel):
    consent_type: ConsentType


class MatchingJobCreate(BaseModel):
    selfie_storage_key: str = Field(min_length=1, max_length=500)


class MatchingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    status: ProcessingStatus
    error_message: str | None


class MatchResultResponse(BaseModel):
    photo_id: str
    similarity: float
    photo_url: str
    favorite: bool = False
