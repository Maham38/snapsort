import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Role(str, enum.Enum):
    organizer = "organizer"
    photographer = "photographer"
    attendee = "attendee"


class EventStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class ConsentType(str, enum.Enum):
    face_matching = "face_matching"


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(Timestamped, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[Role | None] = mapped_column(Enum(Role, name="user_role"))


class Event(Timestamped, Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_organizer_status", "organizer_id", "status"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    organizer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    event_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status"), default=EventStatus.draft
    )


class EventParticipant(Timestamped, Base):
    __tablename__ = "event_participants"
    __table_args__ = (Index("ix_event_participants_event_user", "event_id", "user_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)


class PhotographerAssignment(Timestamped, Base):
    __tablename__ = "photographer_assignments"
    __table_args__ = (Index("ix_assignments_event_photographer", "event_id", "photographer_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    photographer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)


class Photo(Timestamped, Base):
    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    checksum: Mapped[str | None] = mapped_column(String(128), index=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.pending,
    )


class FaceEmbedding(Timestamped, Base):
    __tablename__ = "face_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(512))


class MatchingJob(Timestamped, Base):
    __tablename__ = "matching_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    attendee_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    selfie_storage_key: Mapped[str] = mapped_column(String(500))
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="matching_status"),
        default=ProcessingStatus.pending,
    )
    error_message: Mapped[str | None] = mapped_column(Text)


class MatchResult(Timestamped, Base):
    __tablename__ = "match_results"
    __table_args__ = (
        Index("ix_match_results_job_photo", "matching_job_id", "photo_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    matching_job_id: Mapped[str] = mapped_column(ForeignKey("matching_jobs.id"), index=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    similarity: Mapped[float]


class Favorite(Timestamped, Base):
    __tablename__ = "favorites"
    __table_args__ = (Index("ix_favorites_user_photo", "user_id", "photo_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), index=True)


class ConsentRecord(Timestamped, Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        Index(
            "ix_consent_records_user_event_type",
            "user_id",
            "event_id",
            "consent_type",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    consent_type: Mapped[ConsentType] = mapped_column(
        Enum(ConsentType, name="consent_type")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
