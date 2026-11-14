from datetime import datetime, timezone
import secrets
import string
import uuid
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_user, require_roles
from app.config import get_settings
from app.db import get_db
from app.models import (
    Event,
    EventParticipant,
    EventStatus,
    ConsentRecord,
    ConsentType,
    Favorite,
    MatchResult,
    MatchingJob,
    Photo,
    PhotographerAssignment,
    ProcessingStatus,
    Role,
    User,
)
from app.schemas import (
    EventCreate,
    EventResponse,
    EventUpdate,
    EventJoin,
    ConsentCreate,
    MatchResultResponse,
    MatchingJobCreate,
    MatchingJobResponse,
    SelfieUploadResponse,
    PhotographerAssignmentCreate,
    PhotoResponse,
    RoleUpdate,
    UploadRequest,
    UploadResponse,
    UploadedPhotoResponse,
    UserResponse,
)
from app.storage import create_download_url, create_upload_url, object_exists
from app.jobs import enqueue_matching, enqueue_photo_processing


def _event_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


app = FastAPI(
    title="SnapSort API",
    version="0.1.0",
    description="Authenticated API for SnapSort event photo management.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["DELETE", "GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/me", response_model=UserResponse)
def get_me(user: User = Depends(current_user)) -> User:
    return user


@app.patch("/api/v1/me/role", response_model=UserResponse)
def update_role(
    payload: RoleUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> User:
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@app.post(
    "/api/v1/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    payload: EventCreate,
    user: User = Depends(require_roles(Role.organizer)),
    db: Session = Depends(get_db),
) -> Event:
    for _ in range(3):
        event = Event(
            organizer_id=user.id,
            name=payload.name,
            description=payload.description,
            event_code=_event_code(),
        )
        db.add(event)
        try:
            db.commit()
            db.refresh(event)
            return event
        except IntegrityError:
            db.rollback()
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not allocate a unique event code",
    )


@app.get("/api/v1/events", response_model=list[EventResponse])
def list_events(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[Event]:
    statement = select(Event).where(Event.organizer_id == user.id)
    return list(db.scalars(statement).all())


@app.get("/api/v1/events/{event_id}", response_model=EventResponse)
def get_event(
    event_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.organizer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@app.patch("/api/v1/events/{event_id}", response_model=EventResponse)
def update_event(
    event_id: str,
    payload: EventUpdate,
    user: User = Depends(require_roles(Role.organizer)),
    db: Session = Depends(get_db),
) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.organizer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.status == EventStatus.archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived events cannot be edited",
        )
    event.name = payload.name
    event.description = payload.description
    db.commit()
    db.refresh(event)
    return event


@app.delete("/api/v1/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: str,
    user: User = Depends(require_roles(Role.organizer)),
    db: Session = Depends(get_db),
) -> None:
    event = db.get(Event, event_id)
    if event is None or event.organizer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    db.delete(event)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event cannot be deleted while it contains related records",
        ) from error


@app.post("/api/v1/events/{event_id}/photographers", status_code=status.HTTP_201_CREATED)
def assign_photographer(
    event_id: str,
    payload: PhotographerAssignmentCreate,
    user: User = Depends(require_roles(Role.organizer)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    event = db.get(Event, event_id)
    photographer = db.get(User, payload.photographer_id)
    if event is None or event.organizer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if photographer is None or photographer.role != Role.photographer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Photographer not found")
    assignment = PhotographerAssignment(
        event_id=event_id,
        photographer_id=photographer.id,
    )
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Photographer is already assigned to this event",
        ) from error
    return {"event_id": event_id, "photographer_id": photographer.id}


@app.get("/api/v1/photographer/events", response_model=list[EventResponse])
def photographer_events(
    user: User = Depends(require_roles(Role.photographer)),
    db: Session = Depends(get_db),
) -> list[Event]:
    statement = (
        select(Event)
        .join(PhotographerAssignment, PhotographerAssignment.event_id == Event.id)
        .where(PhotographerAssignment.photographer_id == user.id)
        .order_by(Event.created_at.desc())
    )
    return list(db.scalars(statement).all())


@app.post("/api/v1/photographer/events", response_model=EventResponse)
def join_photographer_event(
    payload: EventJoin,
    user: User = Depends(require_roles(Role.photographer)),
    db: Session = Depends(get_db),
) -> Event:
    event = db.scalar(select(Event).where(Event.event_code == payload.event_code.upper()))
    if event is None or event.status == EventStatus.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    assignment = PhotographerAssignment(
        event_id=event.id,
        photographer_id=user.id,
    )
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return event


@app.post("/api/v1/attendee/events", response_model=EventResponse)
def join_event(
    payload: EventJoin,
    user: User = Depends(require_roles(Role.attendee)),
    db: Session = Depends(get_db),
) -> Event:
    event = db.scalar(select(Event).where(Event.event_code == payload.event_code.upper()))
    if event is None or event.status == EventStatus.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    participant = db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event.id,
            EventParticipant.user_id == user.id,
        )
    )
    if participant is None:
        db.add(EventParticipant(event_id=event.id, user_id=user.id))
        db.commit()
    return event


@app.get("/api/v1/attendee/events", response_model=list[EventResponse])
def attendee_events(
    user: User = Depends(require_roles(Role.attendee)),
    db: Session = Depends(get_db),
) -> list[Event]:
    statement = (
        select(Event)
        .join(EventParticipant, EventParticipant.event_id == Event.id)
        .where(EventParticipant.user_id == user.id, Event.status != EventStatus.archived)
        .order_by(Event.created_at.desc())
    )
    return list(db.scalars(statement).all())


@app.post(
    "/api/v1/attendee/events/{event_id}/selfie-upload",
    response_model=SelfieUploadResponse,
)
def request_selfie_upload(
    event_id: str,
    user: User = Depends(require_roles(Role.attendee)),
    db: Session = Depends(get_db),
) -> SelfieUploadResponse:
    participant = db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.user_id == user.id,
        )
    )
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    storage_key = f"events/{event_id}/selfies/{user.id}/{uuid.uuid4()}.jpg"
    try:
        upload_url = create_upload_url(storage_key, "image/jpeg")
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return SelfieUploadResponse(
        storage_key=storage_key,
        upload_url=upload_url,
        expires_in=get_settings().supabase_signed_url_ttl_seconds,
    )


def _can_upload(event_id: str, user: User, db: Session) -> bool:
    if user.role == Role.organizer:
        event = db.get(Event, event_id)
        return event is not None and event.organizer_id == user.id
    statement = select(PhotographerAssignment).where(
        PhotographerAssignment.event_id == event_id,
        PhotographerAssignment.photographer_id == user.id,
    )
    return db.scalar(statement) is not None


@app.post(
    "/api/v1/events/{event_id}/uploads",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_upload(
    event_id: str,
    payload: UploadRequest,
    user: User = Depends(require_roles(Role.photographer, Role.organizer)),
    db: Session = Depends(get_db),
) -> UploadResponse:
    if not _can_upload(event_id, user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    photo_id = str(uuid.uuid4())
    storage_key = f"events/{event_id}/photos/{photo_id}/{payload.filename}"
    try:
        upload_url = create_upload_url(storage_key, payload.content_type)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    photo = Photo(
        id=photo_id,
        event_id=event_id,
        uploaded_by=user.id,
        storage_key=storage_key,
        checksum=payload.checksum,
        processing_status=ProcessingStatus.pending,
    )
    db.add(photo)
    db.commit()
    return UploadResponse(
        photo_id=photo_id,
        storage_key=storage_key,
        upload_url=upload_url,
        expires_in=get_settings().supabase_signed_url_ttl_seconds,
    )


@app.post("/api/v1/photos/{photo_id}/complete", response_model=PhotoResponse)
def complete_upload(
    photo_id: str,
    user: User = Depends(require_roles(Role.photographer, Role.organizer)),
    db: Session = Depends(get_db),
) -> Photo:
    photo = db.get(Photo, photo_id)
    if photo is None or photo.uploaded_by != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    try:
        uploaded = object_exists(photo.storage_key)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    if not uploaded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Photo has not finished uploading to storage",
        )
    photo.processing_status = ProcessingStatus.pending
    db.commit()
    try:
        enqueue_photo_processing(photo.id)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    db.refresh(photo)
    return photo


@app.get("/api/v1/photographer/uploads", response_model=list[PhotoResponse])
def upload_history(
    user: User = Depends(require_roles(Role.photographer, Role.organizer)),
    db: Session = Depends(get_db),
) -> list[Photo]:
    statement = (
        select(Photo)
        .where(Photo.uploaded_by == user.id)
        .order_by(Photo.created_at.desc())
    )
    return list(db.scalars(statement).all())


@app.get("/api/v1/photographer/photos", response_model=list[UploadedPhotoResponse])
def photographer_photos(
    user: User = Depends(require_roles(Role.photographer, Role.organizer)),
    db: Session = Depends(get_db),
) -> list[UploadedPhotoResponse]:
    statement = select(Photo).where(Photo.uploaded_by == user.id).order_by(Photo.created_at.desc())
    photos = list(db.scalars(statement).all())
    return [
        UploadedPhotoResponse(
            id=photo.id,
            event_id=photo.event_id,
            event_name=db.get(Event, photo.event_id).name,
            storage_key=photo.storage_key,
            checksum=photo.checksum,
            processing_status=photo.processing_status,
            photo_url=create_download_url(photo.storage_key),
        )
        for photo in photos
    ]


@app.post(
    "/api/v1/events/{event_id}/consent",
    status_code=status.HTTP_201_CREATED,
)
def grant_consent(
    event_id: str,
    payload: ConsentCreate,
    user: User = Depends(require_roles(Role.attendee)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    participant = db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.user_id == user.id,
        )
    )
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    record = db.scalar(
        select(ConsentRecord).where(
            ConsentRecord.user_id == user.id,
            ConsentRecord.event_id == event_id,
            ConsentRecord.consent_type == payload.consent_type,
        )
    )
    if record is None:
        record = ConsentRecord(
            user_id=user.id,
            event_id=event_id,
            consent_type=payload.consent_type,
        )
        db.add(record)
    else:
        record.revoked_at = None
    db.commit()
    return {"event_id": event_id, "consent_type": payload.consent_type.value}


@app.delete("/api/v1/events/{event_id}/consent/{consent_type}")
def revoke_consent(
    event_id: str,
    consent_type: ConsentType,
    user: User = Depends(require_roles(Role.attendee)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    records = list(
        db.scalars(
        select(ConsentRecord).where(
            ConsentRecord.event_id == event_id,
            ConsentRecord.user_id == user.id,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.revoked_at.is_(None),
        )
        ).all()
    )
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent not found")
    revoked_at = datetime.now(timezone.utc)
    for record in records:
        record.revoked_at = revoked_at
    db.commit()
    return {"event_id": event_id, "consent_type": consent_type.value, "status": "revoked"}


@app.post(
    "/api/v1/events/{event_id}/matching-jobs",
    response_model=MatchingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_matching_job(
    event_id: str,
    payload: MatchingJobCreate,
    user: User = Depends(require_roles(Role.attendee)),
    db: Session = Depends(get_db),
) -> MatchingJob:
    participant = db.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.user_id == user.id,
        )
    )
    consent = db.scalar(
        select(ConsentRecord).where(
            ConsentRecord.event_id == event_id,
            ConsentRecord.user_id == user.id,
            ConsentRecord.consent_type == ConsentType.face_matching,
            ConsentRecord.revoked_at.is_(None),
        )
    )
    if participant is None or consent is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active face-matching consent is required",
        )
    if not payload.selfie_storage_key.startswith(
        f"events/{event_id}/selfies/{user.id}/"
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid selfie object")
    if not object_exists(payload.selfie_storage_key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selfie upload is incomplete")
    job = MatchingJob(
        event_id=event_id,
        attendee_id=user.id,
        selfie_storage_key=payload.selfie_storage_key,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        enqueue_matching(job.id)
    except RuntimeError as error:
        job.status = ProcessingStatus.failed
        job.error_message = str(error)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return job


@app.get(
    "/api/v1/matching-jobs/{job_id}",
    response_model=MatchingJobResponse,
)
def get_matching_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MatchingJob:
    job = db.get(MatchingJob, job_id)
    if job is None or job.attendee_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matching job not found")
    return job


@app.get(
    "/api/v1/matching-jobs/{job_id}/results",
    response_model=list[MatchResultResponse],
)
def matching_results(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[MatchResult]:
    job = db.get(MatchingJob, job_id)
    if job is None or job.attendee_id != user.id or job.status != ProcessingStatus.complete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matching results not found")
    matches = list(
        db.execute(
            select(MatchResult)
            .where(MatchResult.matching_job_id == job_id)
            .order_by(MatchResult.similarity.desc())
        ).scalars().all()
    )
    response = []
    for match in matches:
        photo = db.get(Photo, match.photo_id)
        if photo is None:
            continue
        try:
            photo_url = create_download_url(photo.storage_key)
        except RuntimeError as error:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
        favorite = db.scalar(
            select(Favorite).where(
                Favorite.user_id == user.id,
                Favorite.photo_id == match.photo_id,
            )
        )
        response.append(
            MatchResultResponse(
                photo_id=match.photo_id,
                similarity=match.similarity,
                photo_url=photo_url,
                favorite=favorite is not None,
            )
        )
    return response


def _authorized_match(
    photo_id: str,
    user: User,
    db: Session,
) -> MatchResult:
    match = db.scalar(
        select(MatchResult)
        .join(MatchingJob, MatchingJob.id == MatchResult.matching_job_id)
        .where(
            MatchResult.photo_id == photo_id,
            MatchingJob.attendee_id == user.id,
            MatchingJob.status == ProcessingStatus.complete,
        )
        .order_by(MatchingJob.created_at.desc())
    )
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return match


@app.get(
    "/api/v1/attendee/events/{event_id}/gallery",
    response_model=list[MatchResultResponse],
)
def attendee_gallery(
    event_id: str,
    user: User = Depends(require_roles(Role.attendee)),
    db: Session = Depends(get_db),
) -> list[MatchResultResponse]:
    statement = (
        select(MatchResult)
        .join(MatchingJob, MatchingJob.id == MatchResult.matching_job_id)
        .where(
            MatchingJob.event_id == event_id,
            MatchingJob.attendee_id == user.id,
            MatchingJob.status == ProcessingStatus.complete,
        )
        .order_by(MatchResult.similarity.desc())
    )
    matches = list(db.scalars(statement).all())
    response: list[MatchResultResponse] = []
    for match in matches:
        photo = db.get(Photo, match.photo_id)
        if photo is None:
            continue
        favorite = db.scalar(
            select(Favorite).where(
                Favorite.user_id == user.id,
                Favorite.photo_id == match.photo_id,
            )
        )
        try:
            photo_url = create_download_url(photo.storage_key)
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error
        response.append(
            MatchResultResponse(
                photo_id=photo.id,
                similarity=match.similarity,
                photo_url=photo_url,
                favorite=favorite is not None,
            )
        )
    return response


@app.post("/api/v1/photos/{photo_id}/favorite", response_model=MatchResultResponse)
def add_favorite(
    photo_id: str,
    user: User = Depends(require_roles(Role.attendee)),
    db: Session = Depends(get_db),
) -> MatchResultResponse:
    match = _authorized_match(photo_id, user, db)
    favorite = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.photo_id == photo_id,
        )
    )
    if favorite is None:
        db.add(Favorite(user_id=user.id, photo_id=photo_id))
        db.commit()
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    try:
        photo_url = create_download_url(photo.storage_key)
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return MatchResultResponse(
        photo_id=photo_id,
        similarity=match.similarity,
        photo_url=photo_url,
        favorite=True,
    )


@app.delete("/api/v1/photos/{photo_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    photo_id: str,
    user: User = Depends(require_roles(Role.attendee)),
    db: Session = Depends(get_db),
) -> None:
    _authorized_match(photo_id, user, db)
    favorite = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.photo_id == photo_id,
        )
    )
    if favorite is not None:
        db.delete(favorite)
        db.commit()
