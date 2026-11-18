import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app import main
from app.auth import require_roles
from app.billing import CheckoutSession, WebhookEvent
from app.db import Base
from app.models import (
    ConsentRecord,
    ConsentType,
    Event,
    EventParticipant,
    EventStatus,
    EventUsage,
    MatchingJob,
    Payment,
    PaymentStatus,
    Photo,
    Plan,
    PlanStatus,
    PlanTier,
    Role,
    User,
)
from app.schemas import UploadRequest


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        User.__table__,
        Plan.__table__,
        Event.__table__,
        EventUsage.__table__,
        Photo.__table__,
        Payment.__table__,
        EventParticipant.__table__,
        ConsentRecord.__table__,
        MatchingJob.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        yield session


def _plan(
    db: Session,
    tier: PlanTier,
    *,
    max_photos: int = 100,
    max_storage_bytes: int = 1000,
    max_matching_searches: int = 2,
) -> Plan:
    plan = Plan(
        tier=tier,
        max_photos=max_photos,
        max_storage_bytes=max_storage_bytes,
        max_matching_searches=max_matching_searches,
        retention_days=30,
        price_cents=4900,
        currency="usd",
        active=True,
    )
    db.add(plan)
    db.commit()
    return plan


def _organizer(db: Session, user_id: str = "organizer") -> User:
    user = User(id=user_id, email=f"{user_id}@example.test", role=Role.organizer)
    db.add(user)
    db.commit()
    return user


def _event(db: Session, organizer: User) -> Event:
    event = Event(
        organizer_id=organizer.id,
        name="Test event",
        event_code=f"CODE{organizer.id[-4:]}",
        status=EventStatus.active,
        plan_tier=PlanTier.standard,
        plan_status=PlanStatus.active,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db.add(event)
    db.flush()
    db.add(EventUsage(event_id=event.id))
    db.commit()
    db.refresh(event)
    return event


def test_one_free_trial_event_per_organizer(db: Session) -> None:
    _plan(db, PlanTier.free_trial)
    organizer = _organizer(db)
    first = main.create_event(
        main.EventCreate(name="First"),
        user=organizer,
        db=db,
    )
    second = main.create_event(
        main.EventCreate(name="Second"),
        user=organizer,
        db=db,
    )

    assert first.plan_tier == PlanTier.free_trial
    assert first.plan_status == PlanStatus.trial
    assert second.plan_tier is None
    assert second.plan_status == PlanStatus.expired


def test_upload_quota_is_enforced(monkeypatch, db: Session) -> None:
    _plan(db, PlanTier.standard, max_photos=1, max_storage_bytes=100)
    organizer = _organizer(db)
    event = _event(db, organizer)
    monkeypatch.setattr(main, "create_upload_url", lambda *_args: "https://upload.test")

    payload = UploadRequest(
        filename="photo.jpg",
        content_type="image/jpeg",
        size_bytes=50,
    )
    main.request_upload(event.id, payload, user=organizer, db=db)

    with pytest.raises(HTTPException) as error:
        main.request_upload(event.id, payload, user=organizer, db=db)
    assert error.value.status_code == 402
    assert "photo limit" in error.value.detail


def test_matching_quota_is_enforced(monkeypatch, db: Session) -> None:
    _plan(db, PlanTier.standard, max_matching_searches=1)
    organizer = _organizer(db)
    event = _event(db, organizer)
    attendee = User(id="attendee", email="attendee@example.test", role=Role.attendee)
    db.add(attendee)
    db.add(EventParticipant(event_id=event.id, user_id=attendee.id))
    db.add(
        ConsentRecord(
            user_id=attendee.id,
            event_id=event.id,
            consent_type=ConsentType.face_matching,
        )
    )
    db.commit()
    monkeypatch.setattr(main, "object_exists", lambda _key: True)
    monkeypatch.setattr(main, "enqueue_matching", lambda _job_id: None)
    payload = main.MatchingJobCreate(
        selfie_storage_key=f"events/{event.id}/selfies/{attendee.id}/selfie.jpg"
    )

    main.create_matching_job(event.id, payload, user=attendee, db=db)
    with pytest.raises(HTTPException) as error:
        main.create_matching_job(event.id, payload, user=attendee, db=db)
    assert error.value.status_code == 402
    assert "matching-search limit" in error.value.detail


class FakePaymentProvider:
    name = "fake"

    def create_checkout_session(self, *, event, plan, payment_id):
        return CheckoutSession(
            provider_ref=f"session-{payment_id}",
            checkout_url="https://checkout.test",
        )

    def verify_webhook(self, payload, signature):
        if signature != "valid":
            raise ValueError("Invalid webhook signature")
        return WebhookEvent(
            provider_ref="session-1",
            status=PaymentStatus.paid,
            event_id=self.event_id,
            tier=PlanTier.standard,
        )


def _request() -> Request:
    async def receive():
        return {"type": "http.request", "body": b"payload", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/billing/webhook",
            "headers": [],
        },
        receive,
    )


def test_webhook_is_idempotent_and_rejects_bad_signature(monkeypatch, db: Session) -> None:
    _plan(db, PlanTier.standard)
    organizer = _organizer(db)
    event = _event(db, organizer)
    payment = Payment(
        event_id=event.id,
        organizer_id=organizer.id,
        provider="fake",
        provider_ref="session-1",
        amount=4900,
        currency="usd",
    )
    db.add(payment)
    db.commit()
    provider = FakePaymentProvider()
    provider.event_id = event.id
    monkeypatch.setattr(main, "get_payment_provider", lambda: provider)

    with pytest.raises(HTTPException) as error:
        asyncio.run(main.billing_webhook(_request(), "invalid", db))
    assert error.value.status_code == 400

    first = asyncio.run(main.billing_webhook(_request(), "valid", db))
    second = asyncio.run(main.billing_webhook(_request(), "valid", db))
    assert first.status == PaymentStatus.paid
    assert second.status == PaymentStatus.paid
    db.refresh(event)
    assert event.plan_status == PlanStatus.active


def test_checkout_requires_ownership_and_organizer_role(db: Session) -> None:
    _plan(db, PlanTier.standard)
    owner = _organizer(db)
    event = _event(db, owner)
    other = _organizer(db, "other")
    with pytest.raises(HTTPException) as ownership_error:
        main.get_event_plan(event.id, user=other, db=db)
    assert ownership_error.value.status_code == 404

    attendee = User(id="attendee", email="role@example.test", role=Role.attendee)
    db.add(attendee)
    db.commit()
    with pytest.raises(HTTPException) as role_error:
        require_roles(Role.organizer)(attendee)
    assert role_error.value.status_code == 403
