"""Billing providers, plan helpers, and retention maintenance."""

from __future__ import annotations

import hashlib
import hmac
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Event, EventUsage, PaymentStatus, Plan, PlanStatus, PlanTier


@dataclass(frozen=True)
class CheckoutSession:
    provider_ref: str
    checkout_url: str


@dataclass(frozen=True)
class WebhookEvent:
    provider_ref: str
    status: PaymentStatus
    event_id: str
    tier: PlanTier


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_checkout_session(
        self,
        *,
        event: Event,
        plan: Plan,
        payment_id: str,
    ) -> CheckoutSession:
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> WebhookEvent:
        raise NotImplementedError


class StripePaymentProvider(PaymentProvider):
    name = "stripe"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
            raise RuntimeError(
                "Stripe is not configured. Set STRIPE_SECRET_KEY and "
                "STRIPE_WEBHOOK_SECRET."
            )
        self._secret_key = settings.stripe_secret_key
        self._webhook_secret = settings.stripe_webhook_secret
        self._tolerance = settings.stripe_webhook_tolerance_seconds

    def create_checkout_session(
        self,
        *,
        event: Event,
        plan: Plan,
        payment_id: str,
    ) -> CheckoutSession:
        data = {
            "mode": "payment",
            "success_url": get_settings().stripe_success_url,
            "cancel_url": get_settings().stripe_cancel_url,
            "client_reference_id": payment_id,
            "metadata[event_id]": event.id,
            "metadata[plan_tier]": plan.tier.value,
            "metadata[payment_id]": payment_id,
            "line_items[0][price_data][currency]": plan.currency,
            "line_items[0][price_data][product_data][name]": (
                f"SnapSort {plan.tier.value} event"
            ),
            "line_items[0][price_data][unit_amount]": str(plan.price_cents),
            "line_items[0][quantity]": "1",
        }
        try:
            response = httpx.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=data,
                auth=(self._secret_key, ""),
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError("Stripe could not create a checkout session") from error
        provider_ref = result.get("id")
        checkout_url = result.get("url")
        if not provider_ref or not checkout_url:
            raise RuntimeError("Stripe returned an incomplete checkout session")
        return CheckoutSession(provider_ref=provider_ref, checkout_url=checkout_url)

    def verify_webhook(self, payload: bytes, signature: str) -> WebhookEvent:
        timestamp, signatures = _parse_stripe_signature(signature)
        now = int(datetime.now(UTC).timestamp())
        if abs(now - timestamp) > self._tolerance:
            raise ValueError("Stripe webhook signature has expired")
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(
            self._webhook_secret.encode(),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        if not any(hmac.compare_digest(expected, value) for value in signatures):
            raise ValueError("Invalid Stripe webhook signature")
        try:
            event = json.loads(payload)
            session = event["data"]["object"]
            metadata = session["metadata"]
            provider_ref = session["id"]
            event_id = metadata["event_id"]
            tier = PlanTier(metadata["plan_tier"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("Stripe webhook payload is invalid") from error
        event_type = event.get("type")
        status = (
            PaymentStatus.paid
            if event_type == "checkout.session.completed"
            and session.get("payment_status") == "paid"
            else PaymentStatus.failed
        )
        return WebhookEvent(
            provider_ref=provider_ref,
            status=status,
            event_id=event_id,
            tier=tier,
        )


def _parse_stripe_signature(signature: str) -> tuple[int, list[str]]:
    values: dict[str, list[str]] = {}
    for item in signature.split(","):
        key, separator, value = item.partition("=")
        if separator:
            values.setdefault(key, []).append(value)
    try:
        timestamp = int(values["t"][0])
        signatures = values["v1"]
    except (KeyError, IndexError, ValueError) as error:
        raise ValueError("Stripe webhook signature is malformed") from error
    return timestamp, signatures


def get_payment_provider() -> PaymentProvider:
    return StripePaymentProvider()


def get_plan(db: Session, tier: PlanTier) -> Plan | None:
    return db.get(Plan, tier)


def active_plan_for_event(db: Session, event: Event) -> Plan | None:
    if event.plan_tier is None or event.plan_status == PlanStatus.expired:
        return None
    expires_at = event.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at is not None and expires_at <= datetime.now(UTC):
        return None
    return get_plan(db, event.plan_tier)


def get_or_create_usage(db: Session, event_id: str, *, lock: bool = False) -> EventUsage:
    statement = select(EventUsage).where(EventUsage.event_id == event_id)
    if lock:
        statement = statement.with_for_update()
    usage = db.scalar(statement)
    if usage is None:
        usage = EventUsage(event_id=event_id)
        db.add(usage)
        db.flush()
    return usage


def activate_event_plan(
    db: Session,
    *,
    event: Event,
    plan: Plan,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(UTC)
    event.plan_tier = plan.tier
    event.plan_status = (
        PlanStatus.trial if plan.tier == PlanTier.free_trial else PlanStatus.active
    )
    event.expires_at = current + timedelta(days=plan.retention_days)
    event.retention_review_required = False


def expire_plans_and_flag_retention(db: Session, now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    expired = db.execute(
        update(Event)
        .where(
            Event.plan_status.in_([PlanStatus.trial, PlanStatus.active]),
            Event.expires_at.is_not(None),
            Event.expires_at <= current,
        )
        .values(plan_status=PlanStatus.expired)
    ).rowcount
    events = db.scalars(
        select(Event).where(
            Event.plan_tier.is_not(None),
            Event.expires_at.is_not(None),
            Event.retention_review_required.is_(False),
        )
    ).all()
    for event in events:
        plan = get_plan(db, event.plan_tier)
        expires_at = event.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if plan is not None and expires_at is not None and expires_at + timedelta(days=plan.retention_days) <= current:
            event.retention_review_required = True
    db.commit()
    return expired or 0
