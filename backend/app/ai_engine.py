
from functools import lru_cache
from io import BytesIO

import numpy as np
from PIL import Image

from app.config import get_settings


@lru_cache
def face_model():
    settings = get_settings()

    try:
        from insightface.app import FaceAnalysis
    except ImportError as error:
        raise RuntimeError(
            "AI runtime is not installed. Install backend[ai] before processing faces."
        ) from error

    model_kwargs = {
        "name": settings.ai_model_name,
        "providers": ["CPUExecutionProvider"],
    }

    if settings.ai_model_root:
        model_kwargs["root"] = settings.ai_model_root

    model = FaceAnalysis(**model_kwargs)
    model.prepare(ctx_id=0, det_size=(640, 640))

    return model


def _detect_faces(image_bytes: bytes):
    try:
        image = np.asarray(
            Image.open(BytesIO(image_bytes)).convert("RGB")
        )
    except Exception as error:
        raise ValueError("Uploaded object is not a readable image") from error

    return face_model().get(image[:, :, ::-1])


def face_embeddings_from_image(image_bytes: bytes) -> list[list[float]]:
    """Extract embeddings for all detectable faces in an event photo."""
    faces = _detect_faces(image_bytes)

    embeddings = []

    for face in faces:
        embedding = face.normed_embedding

        if embedding is None or len(embedding) != 512:
            continue

        embeddings.append(embedding.astype(float).tolist())

    if not embeddings:
        raise ValueError("No valid faces detected in the event photo")

    return embeddings


def embedding_from_selfie(image_bytes: bytes) -> list[float]:
    """Extract exactly one face embedding from an attendee selfie."""
    faces = _detect_faces(image_bytes)

    if len(faces) != 1:
        raise ValueError("Selfie must contain exactly one detectable face")

    embedding = faces[0].normed_embedding

    if embedding is None or len(embedding) != 512:
        raise ValueError("Face model returned an invalid embedding")

    return embedding.astype(float).tolist()
