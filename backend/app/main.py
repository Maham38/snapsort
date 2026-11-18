from datetime import datetime, timedelta, timezone
import secrets
import string
import uuid
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_user, require_roles
from app.billing import (
    activate_event_plan,
    active_plan_for_event,
    get_or_create_usage,
    get_payment_provider,
    get_plan,
)
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
    EventUsage,
    Payment,
    PaymentStatus,
    Plan,
    PlanStatus,
    PlanTier,
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
    CheckoutRequest,
    CheckoutResponse,
    EventPlanResponse,
    PaymentResponse,
    PlanResponse,
    UsageResponse,
)
from app.storage import (
    create_download_url,
    create_upload_url,
    object_exists,
    object_size,
)
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


def _owned_event(event_id: str, user: User, db: Session) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.organizer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


def _plan_response(plan) -> PlanResponse:
    return PlanResponse(
        tier=plan.tier,
        max_photos=plan.max_photos,
        max_storage_bytes=plan.max_storage_bytes,
        max_matching_searches=plan.max_matching_searches,
        retention_days=plan.retention_days,
        price_cents=plan.price_cents,
        currency=plan.currency,
    )


def _event_plan_response(event: Event, plan, usage: EventUsage) -> EventPlanResponse:
    return EventPlanResponse(
        tier=event.plan_tier,
        status=event.plan_status,
        expires_at=event.expires_at,
        limits=_plan_response(plan) if plan is not None else None,
        usage=UsageResponse(
            photo_count=usage.photo_count,
            storage_bytes=usage.storage_bytes,
            matching_searches=usage.matching_searches,
        ),
    )


def _require_event_plan(event: Event, db: Session):
    plan = active_plan_for_event(db, event)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="This event needs an active plan before it can accept uploads or matching searches.",
        )
    return plan


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
    trial_plan = db.scalar(
        select(Plan).where(
            Plan.tier == PlanTier.free_trial,
            Plan.active.is_(True),
        )
    )
    has_trial = db.scalar(
        select(Event.id)
        .where(
            Event.organizer_id == user.id,
            Event.plan_tier == PlanTier.free_trial,
        )
        .limit(1)
    ) is not None
    for _ in range(3):
        event = Event(
            organizer_id=user.id,
            name=payload.name,
            description=payload.description,
            event_code=_event_code(),
            plan_tier=PlanTier.free_trial if not has_trial and trial_plan else None,
            plan_status=PlanStatus.trial if not has_trial and trial_plan else PlanStatus.expired,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(days=trial_plan.retention_days)
                if not has_trial and trial_plan
                else None
            ),
        )
        db.add(event)
        try:
            db.commit()
            get_or_create_usage(db, event.id)
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


@app.get("/api/v1/plans", response_model=list[PlanResponse])
def list_plans(
    user: User = Depends(require_roles(Role.organizer)),
    db: Session = Depends(get_db),
) -> list[Plan]:
    return list(
        db.scalars(select(Plan).where(Plan.active.is_(True)).order_by(Plan.price_cents))
        .all()
    )


@app.get("/api/v1/events/{event_id}/plan", response_model=EventPlanResponse)
def get_event_plan(
    event_id: str,
    user: User = Depends(require_roles(Role.organizer)),
    db: Session = Depends(get_db),
) -> EventPlanResponse:
    event = _owned_event(event_id, user, db)
    return _event_plan_response(
        event,
        get_plan(db, event.plan_tier) if event.plan_tier else None,
        get_or_create_usage(db, event.id),
    )


@app.post("/api/v1/events/{event_id}/checkout", response_model=CheckoutResponse)
def create_checkout(
    event_id: str,
    payload: CheckoutRequest,
    user: User = Depends(require_roles(Role.organizer)),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    event = _owned_event(event_id, user, db)
    if payload.tier in (PlanTier.free_trial, PlanTier.enterprise):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free trial is assigned automatically; enterprise plans require manual activation.",
        )
    plan = get_plan(db, payload.tier)
    if plan is None or not plan.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    payment = Payment(
        event_id=event.id,
        organizer_id=user.id,
        provider="stripe",
        provider_ref=f"pending:{uuid.uuid4()}",
        amount=plan.price_cents,
        currency=plan.currency,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    db.flush()
    try:
        provider = get_payment_provider()
        checkout = provider.create_checkout_session(
            event=event,
            plan=plan,
            payment_id=payment.id,
        )
    except RuntimeError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    payment.provider_ref = checkout.provider_ref
    db.commit()
    return CheckoutResponse(
        payment_id=payment.id,
        checkout_url=checkout.checkout_url,
        provider=provider.name,
        expires_at=event.expires_at,
    )


@app.post("/api/v1/billing/webhook", response_model=PaymentResponse)
async def billing_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> PaymentResponse:
    if not stripe_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook signature required")
    try:
        provider = get_payment_provider()
        webhook = provider.verify_webhook(await request.body(), stripe_signature)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    payment = db.scalar(
        select(Payment).where(
            Payment.provider == provider.name,
            Payment.provider_ref == webhook.provider_ref,
        )
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.status == PaymentStatus.paid:
        return PaymentResponse(payment_id=payment.id, status=payment.status)
    if payment.event_id != webhook.event_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment event mismatch")
    event = db.get(Event, payment.event_id)
    plan = get_plan(db, webhook.tier)
    if event is None or plan is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment plan is invalid")
    payment.status = webhook.status
    if webhook.status == PaymentStatus.paid:
        activate_event_plan(db, event=event, plan=plan)
    db.commit()
    return PaymentResponse(payment_id=payment.id, status=payment.status)


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
    event = db.get(Event, event_id)
    if event is None or not _can_upload(event_id, user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    plan = _require_event_plan(event, db)
    settings = get_settings()
    if payload.size_bytes > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Each photo must be {settings.max_upload_size_bytes} bytes or smaller.",
        )
    usage = get_or_create_usage(db, event.id, lock=True)
    pending_count, pending_bytes = db.execute(
        select(
            func.count(Photo.id),
            func.coalesce(func.sum(Photo.size_bytes), 0),
        ).where(
            Photo.event_id == event.id,
            Photo.usage_counted.is_(False),
            Photo.processing_status != ProcessingStatus.failed,
        )
    ).one()
    if usage.photo_count + pending_count + 1 > plan.max_photos:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="This event has reached its photo limit. Upgrade the event plan.",
        )
    if usage.storage_bytes + int(pending_bytes) + payload.size_bytes > plan.max_storage_bytes:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="This event has reached its storage limit. Upgrade the event plan.",
        )
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
        size_bytes=payload.size_bytes,
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
    try:
        actual_size = object_size(photo.storage_key)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    if actual_size > get_settings().max_upload_size_bytes or actual_size > photo.size_bytes:
        photo.processing_status = ProcessingStatus.failed
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded photo exceeds the size reserved for this event.",
        )
    if not photo.usage_counted:
        usage = get_or_create_usage(db, photo.event_id, lock=True)
        event = db.get(Event, photo.event_id)
        if event is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        plan = _require_event_plan(event, db)
        if (
            usage.photo_count + 1 > plan.max_photos
            or usage.storage_bytes + actual_size > plan.max_storage_bytes
        ):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="This event has reached its plan quota.",
            )
        photo.size_bytes = actual_size
        usage.photo_count += 1
        usage.storage_bytes += actual_size
        photo.usage_counted = True
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
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    plan = _require_event_plan(event, db)
    if not payload.selfie_storage_key.startswith(
        f"events/{event_id}/selfies/{user.id}/"
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid selfie object")
    if not object_exists(payload.selfie_storage_key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selfie upload is incomplete")
    usage = get_or_create_usage(db, event_id, lock=True)
    if usage.matching_searches >= plan.max_matching_searches:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="This event has reached its matching-search limit. Upgrade the event plan.",
        )
    job = MatchingJob(
        event_id=event_id,
        attendee_id=user.id,
        selfie_storage_key=payload.selfie_storage_key,
    )
    usage.matching_searches += 1
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
