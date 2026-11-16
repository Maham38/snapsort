
import json
import logging
from time import sleep

from sqlalchemy import delete, func, select

from app.ai_engine import (
    embedding_from_selfie,
    face_embeddings_from_image,
)
from app.config import get_settings
from app.db import SessionLocal
from app.jobs import MATCHING_QUEUE, PHOTO_QUEUE, redis_client
from app.models import (
    FaceEmbedding,
    MatchResult,
    MatchingJob,
    Photo,
    ProcessingStatus,
)
from app.storage import download_object

logger = logging.getLogger(__name__)


def _process_photo(photo_id: str) -> None:
    with SessionLocal() as db:
        photo = db.get(Photo, photo_id)

        if photo is None:
            return

        photo.processing_status = ProcessingStatus.processing
        db.commit()

        try:
            image = download_object(photo.storage_key)

            # Extract embeddings for every detectable face.
            embeddings = face_embeddings_from_image(image)

            # Remove previous embeddings to make reprocessing safer.
            db.execute(
                delete(FaceEmbedding).where(
                    FaceEmbedding.photo_id == photo.id
                )
            )

            db.add_all(
                FaceEmbedding(
                    photo_id=photo.id,
                    event_id=photo.event_id,
                    embedding=embedding,
                )
                for embedding in embeddings
            )

            photo.processing_status = ProcessingStatus.complete
            db.commit()

            logger.info(
                "Photo %s processed successfully: %s faces detected",
                photo.id,
                len(embeddings),
            )

        except Exception:
            db.rollback()

            photo = db.get(Photo, photo_id)

            if photo is not None:
                photo.processing_status = ProcessingStatus.failed
                db.commit()

            logger.exception("Photo processing failed for %s", photo_id)


def _process_matching(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(MatchingJob, job_id)

        if job is None:
            return

        job.status = ProcessingStatus.processing
        db.commit()

        try:
            image = download_object(job.selfie_storage_key)

            # An attendee selfie must contain exactly one face.
            embedding = embedding_from_selfie(image)

            distance = FaceEmbedding.embedding.cosine_distance(embedding)

            # One result per photo, using its closest matching face.
            matches = db.execute(
                select(
                    FaceEmbedding.photo_id,
                    func.min(distance).label("distance"),
                )
                .where(
                    FaceEmbedding.event_id == job.event_id,
                    distance <= 1 - get_settings().ai_match_threshold,
                )
                .group_by(FaceEmbedding.photo_id)
                .order_by(func.min(distance))
            ).all()

            # Make processing the same job idempotent.
            db.execute(
                delete(MatchResult).where(
                    MatchResult.matching_job_id == job.id
                )
            )

            db.add_all(
                MatchResult(
                    matching_job_id=job.id,
                    photo_id=photo_id,
                    event_id=job.event_id,
                    similarity=max(0.0, 1 - float(distance_value)),
                )
                for photo_id, distance_value in matches
            )

            job.status = ProcessingStatus.complete
            job.error_message = None
            db.commit()

            logger.info(
                "Matching job %s completed: %s photos matched",
                job.id,
                len(matches),
            )

        except Exception as error:
            db.rollback()

            job = db.get(MatchingJob, job_id)

            if job is not None:
                job.status = ProcessingStatus.failed
                job.error_message = str(error)[:2000]
                db.commit()

            logger.exception("Matching failed for %s", job_id)


def run() -> None:
    client = redis_client()
    client.ping()
    logger.info("Redis connection successful")

    queues = {
        MATCHING_QUEUE: _process_matching,
        PHOTO_QUEUE: _process_photo,
    }

    logger.info("SnapSort worker started")

    while True:
        item = client.blpop(list(queues), timeout=5)

        if item is None:
            continue

        queue, payload = item

        try:
            key = "job_id" if queue == MATCHING_QUEUE else "photo_id"
            queues[queue](json.loads(payload)[key])

        except Exception:
            logger.exception("Worker item failed from %s", queue)
            sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
