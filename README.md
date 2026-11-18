# SnapSort

### Find your photos, without the scrolling.

SnapSort is an AI-powered event photo discovery application that helps attendees find photographs of themselves in large event galleries. Instead of manually browsing hundreds or thousands of pictures, attendees join an event, provide a selfie with explicit consent, and receive a personalized collection of matching photos.

SnapSort combines a Flutter mobile application, FastAPI backend, computer vision-based face matching, vector similarity search, and secure cloud photo storage.

> **Project Status:** Active Development  
> **Platform:** Android (Flutter)  
> **Domain:** Artificial Intelligence / Computer Vision  
> **Category:** Event Photography & Photo Discovery

---

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Objectives](#objectives)
- [How It Works](#how-it-works)
- [Features](#features)
- [User Roles](#user-roles)
- [AI and Computer Vision](#ai-and-computer-vision)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Installation and Setup](#installation-and-setup)
- [Environment Configuration](#environment-configuration)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Deployment](#deployment)
- [Security and Privacy](#security-and-privacy)
- [Limitations](#limitations)
- [Business Model](#business-model)
- [Future Roadmap](#future-roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Event photographers capture hundreds or thousands of photographs at weddings, birthdays, university events, conferences, parties, and other gatherings. However, finding an individual photograph within a large event gallery can be time-consuming and frustrating.

SnapSort simplifies this experience through AI-powered facial matching.

Organizers create events, photographers upload event photographs, and attendees use a selfie to find photographs in which they appear. The system processes images, detects faces, generates facial embeddings, and retrieves potential matches from the relevant event gallery.

### Vision

To make event photo discovery effortless by connecting people with their memories through intelligent, secure, and personalized photo retrieval.

---

## Problem Statement

Traditional event photo-sharing methods often require attendees to manually browse large galleries to find their photographs.

This creates several challenges:

- Manually searching large photo collections is time-consuming.
- Attendees may miss photographs in which they appear.
- Organizers face difficulties distributing photographs efficiently.
- Photographers may need to repeatedly share or organize large collections.
- The photo discovery experience becomes less convenient as gallery size increases.

SnapSort addresses these problems by automating personalized photo discovery using computer vision and event-scoped facial matching.

---

## Objectives

- Automate the discovery of event photographs.
- Reduce the time required to find personal photographs.
- Provide a personalized photo gallery for each attendee.
- Simplify event photo management for organizers and photographers.
- Support secure photo uploads and downloads.
- Implement event-specific facial matching with explicit user consent.
- Process large photo collections asynchronously.
- Maintain privacy through authorization, event isolation, and secure storage.

---

## How It Works

1. **Create an Event** — The organizer creates an event and generates a unique event code.
2. **Share Event Access** — Attendees and photographers join through the event code or supported event access flow.
3. **Upload Photos** — Photographers upload event photographs to secure cloud storage.
4. **AI Processing** — The backend queues uploaded images for face detection and embedding generation.
5. **Join the Event** — Attendees enter the event code to access the event.
6. **Give Consent** — Attendees explicitly consent to facial matching for that event.
7. **Submit a Selfie** — The attendee uploads a selfie to initiate the matching process.
8. **Find Matches** — The AI system compares the selfie embedding with embeddings from photographs belonging to the event.
9. **View My Photos** — Potential matching photographs are displayed in the attendee's personalized gallery.
10. **Save and Share** — Attendees can favorite, download, or share their photographs.

---

## Features

### Authentication and User Management

- Firebase Authentication integration.
- Email and password registration.
- Secure sign-in.
- Password reset functionality.
- Persistent authentication sessions.
- User profile management.
- Role selection.
- Backend Firebase token verification.

### Event Management

- Create events.
- View events.
- Update event information.
- Delete events.
- Generate unique event codes.
- QR code/event code sharing.
- Event-based access management.
- Organizer ownership validation.

### Photographer Features

- Join events using event codes.
- Access assigned or authorized events.
- Upload multiple photographs.
- Support for JPG, JPEG, PNG, and WebP formats.
- Upload progress tracking.
- Upload retry handling.
- Upload history metadata.

### Attendee Features

- Join events using event codes.
- View joined events.
- Provide event-specific matching consent.
- Revoke consent.
- Upload a selfie.
- Initiate face-matching jobs.
- Track matching progress.
- View personalized matching results.

### Personalized Photo Gallery

- View matched photographs.
- Lazy-loaded photo gallery.
- Favorite and unfavorite photographs.
- Download photos to the device.
- Share photographs.
- Access event-organized photo results.

### Personal Gallery

- Optional local photo-library scanning.
- Permission-based device photo access.
- Scan images locally without uploading them to SnapSort.
- Deduplicate scanned images.
- Exclude unwanted photos.
- Save selected images to the SnapSort album.

### Billing and Event Plans

- Organizer-focused event billing model.
- Pay-per-event pricing structure.
- Event plan management.
- Usage limits and quotas.
- Stripe Checkout integration when configured.
- Server-side payment webhook verification.

---

## User Roles

| Role | Description |
|---|---|
| **Organizer** | Creates and manages events, shares event codes, manages event plans, and oversees event photo delivery. |
| **Photographer** | Joins authorized events and uploads event photographs. |
| **Attendee** | Joins events, provides consent, submits selfies, and views personalized photographs. |

Protected actions are validated by the backend rather than relying solely on the mobile application's UI.

---

## AI and Computer Vision

SnapSort uses **Computer Vision and Machine Learning** for facial detection, facial representation, and similarity-based photo retrieval.

It does not currently rely on a generative AI chatbot, Large Language Model (LLM), or Retrieval-Augmented Generation (RAG) pipeline for its core photo-matching functionality.

### Face-Matching Pipeline

\`\`\`text
         EVENT PHOTOGRAPHS
                |
                v
       Private Cloud Storage
                |
                v
       Background Job Queue
             (Redis)
                |
                v
        Face Detection
          (InsightFace)
                |
                v
      Embedding Extraction
        (512 Dimensions)
                |
                v
    PostgreSQL + pgvector
                |
                |
        ATTENDEE SELFIE
                |
                v
      Face Detection + Embedding
                |
                v
       Vector Similarity Search
                |
                v
     Event-Scoped Photo Matching
                |
                v
       Personalized Photo Gallery
\`\`\`

### AI Technologies

| Technology | Purpose |
|---|---|
| **InsightFace** | Face detection and face representation |
| **ONNX Runtime** | Machine learning inference |
| **Face Embeddings** | Numerical representation of detected faces |
| **512-Dimensional Vectors** | Facial feature representations |
| **pgvector** | Vector storage and similarity search |
| **Cosine/Vector Similarity** | Retrieve potentially similar face representations |
| **Redis** | Background processing queues |

### Processing Strategy

- Uploaded photographs are processed asynchronously.
- Face detection identifies faces present in images.
- Face embeddings are generated using the configured AI model.
- Embeddings are stored in PostgreSQL using pgvector.
- Attendee selfie embeddings are compared against embeddings from the relevant event.
- Potential matches are returned through authorized matching results.

Facial matching is probabilistic. Results may include false positives or false negatives and must not be treated as identity verification.

---

## System Architecture

SnapSort follows a mobile-client and backend-service architecture with separate asynchronous AI processing.

\`\`\`text
+----------------------------------+
|         Flutter Mobile App       |
|                                  |
|  Organizer | Photographer         |
|  Attendee  | Personal Gallery   |
+----------------+-----------------+
                 |
                 | HTTPS REST API
                 | Firebase ID Token
                 v
+----------------------------------+
|          FastAPI Backend        |
|                                  |
| Authentication & Authorization    |
| Event Management                |
| Upload Management              |
| Matching Jobs                  |
| Gallery & Favorites            |
| Billing & Usage               |
+----------+------------+---------+
           |            |
           v            v
    PostgreSQL       Supabase
     + pgvector      Storage
           |
           v
         Redis
      Job Queues
           |
           v
+----------------------------------+
|      Background AI Worker       |
|                                  |
| Photo Processing                |
| Face Detection                  |
| Embedding Generation            |
| Face Matching                  |
+----------------------------------+
\`\`\`

### Architectural Principles

- REST API communication.
- Firebase-based authentication.
- Backend-enforced authorization.
- Event-scoped access control.
- Asynchronous image processing.
- Secure cloud object storage.
- Temporary signed URLs.
- Database schema migrations.
- Separation of mobile, backend, and worker responsibilities.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Mobile Application | Flutter, Dart |
| Frontend Architecture | Feature-based application structure |
| Backend | Python, FastAPI |
| API | REST, OpenAPI |
| Authentication | Firebase Authentication |
| User Profiles | Firestore |
| Database | PostgreSQL |
| Vector Database Extension | pgvector |
| ORM | SQLAlchemy |
| Database Migrations | Alembic |
| AI / Computer Vision | InsightFace |
| AI Inference Runtime | ONNX Runtime |
| Face Embeddings | 512-dimensional embeddings |
| Background Jobs | Redis, Python Worker |
| Cloud Storage | Supabase Storage |
| Data Validation | Pydantic |
| Backend Testing | Pytest |
| Mobile Testing | Flutter Test |
| Containerization | Docker |
| Deployment | Railway |
| Version Control | Git, GitHub |
| Payment Integration | Stripe Checkout and Webhooks |

---

## Project Structure

\`\`\`text
SnapSort/
│
├── lib/                          # Flutter mobile application
│   ├── main.dart
│   ├── services/                  # API and authentication services
│   ├── ...
│   │
├── android/                        # Android-specific configuration
│
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI application
│   │   ├── models.py                # SQLAlchemy database models
│   │   ├── schemas.py               # Pydantic schemas
│   │   ├── storage.py                # Storage integration
│   │   ├── worker.py                 # Background processing
│   │   └── ...
│   │
│   ├── migrations/                  # Alembic migrations
│   ├── tests/                       # Backend test suite
│   ├── scripts/                      # Utility scripts
│   └── .env.example                  # Environment template
│
├── test/                             # Flutter tests
├── pubspec.yaml                      # Flutter dependencies
└── README.md
\`\`\`

*This structure is an overview. Individual files and modules may evolve during development.*

---

## Installation and Setup

### Prerequisites

Install the following before setting up SnapSort:

- Git
- Flutter SDK
- Dart SDK
- Python
- PostgreSQL
- pgvector extension
- Redis
- Firebase CLI
- FlutterFire CLI

### 1. Clone the Repository

\`\`\`bash
git clone https://github.com/Maham38/snapsort.git
cd snapsort
\`\`\`

### 2. Install Flutter Dependencies

\`\`\`bash
flutter pub get
\`\`\`

### 3. Configure Firebase

Install FlutterFire CLI:

\`\`\`bash
dart pub global activate flutterfire_cli
\`\`\`

Sign in to Firebase:

\`\`\`bash
firebase login
\`\`\`

Configure Firebase for the Flutter project:

\`\`\`bash
flutterfire configure
\`\`\`

In the Firebase Console:

- Enable Email/Password authentication.
- Configure the Firestore database.
- Configure the Android Firebase application.
- Review and deploy Firestore security rules.

### 4. Run the Flutter Application

\`\`\`bash
flutter run
\`\`\`

For a physical Android device connected to the same network as your computer:

\`\`\`bash
flutter run --dart-define=SNAPSORT_API_BASE_URL=http://<computer-lan-ip>:8000
\`\`\`

For Android emulators, the local computer API is typically accessible using:

\`\`\`text
http://10.0.2.2:8000
\`\`\`

For a USB-connected Android device, ADB port forwarding can be used:

\`\`\`bash
adb reverse tcp:8000 tcp:8000

flutter run --dart-define=SNAPSORT_API_BASE_URL=http://127.0.0.1:8000
\`\`\`

### 5. Backend Setup

Navigate to the backend directory:

\`\`\`bash
cd backend
\`\`\`

Create a Python virtual environment:

\`\`\`powershell
python -m venv .venv
\`\`\`

Activate it:

\`\`\`powershell
.\\.venv\\Scripts\\Activate.ps1
\`\`\`

Install backend dependencies:

\`\`\`bash
python -m pip install -e ".[test]"
\`\`\`

Create the environment configuration file:

\`\`\`powershell
Copy-Item .env.example .env
\`\`\`

Configure the required database, Redis, Firebase, and storage settings in `backend/.env`.

Run database migrations:

\`\`\`bash
alembic upgrade head
\`\`\`

Start the backend API:

\`\`\`bash
uvicorn app.main:app --reload
\`\`\`

The local API will be available at:

| Service | URL |
|---|---|
| API | http://127.0.0.1:8000 |
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |

### 6. Start the AI Worker

Install AI dependencies:

\`\`\`bash
python -m pip install -e ".[ai,test]"
\`\`\`

Ensure PostgreSQL, Redis, Supabase Storage, and the AI model configuration are available.

Start the background worker in a separate terminal:

\`\`\`bash
cd backend
python -m app.worker
\`\`\`

The first AI model initialization may download required InsightFace model files.

---

## Environment Configuration

Use `backend/.env.example` as the reference for required configuration variables.

The backend environment may include:

| Variable Category | Purpose |
|---|---|
| Database configuration | PostgreSQL connection |
| Redis configuration | Background queue connectivity |
| Firebase credentials | Server-side authentication verification |
| Supabase URL | Storage service endpoint |
| Supabase secret key | Backend storage access |
| Storage bucket name | Event photo storage |
| Signed URL expiration | Temporary upload/download access |
| AI model configuration | Model files and cache location |
| Stripe configuration | Billing and webhook integration |

### Supabase Storage Setup

Create a private Supabase Storage bucket named:

\`\`\`text
event-photos
\`\`\`

Configure the backend with the appropriate Supabase URL, server-side secret, bucket name, and signed URL expiration.

SnapSort uses temporary signed URLs for photo uploads. The backend verifies uploaded objects before accepting them for processing.

**Never commit real secrets, private keys, service account files, or production environment variables.**

---

## API Documentation

SnapSort uses FastAPI to provide REST API endpoints.

When the backend is running, interactive API documentation is available:

| Documentation | Endpoint |
|---|---|
| Swagger UI | `/docs` |
| ReDoc | `/redoc` |
| OpenAPI JSON | `/openapi.json` |

### API Modules

- Authentication and user profile.
- User roles.
- Event management.
- Event joining and participation.
- Photographer uploads.
- Photo processing.
- Consent management.
- Face-matching jobs.
- Matching results.
- Personal gallery.
- Favorites.
- Billing and event plans.

### Representative Matching Endpoints

\`\`\`http
POST   /api/v1/events/{event_id}/consent
DELETE /api/v1/events/{event_id}/consent/{consent_type}
POST   /api/v1/events/{event_id}/matching-jobs
GET    /api/v1/matching-jobs/{job_id}
GET    /api/v1/matching-jobs/{job_id}/results
\`\`\`

For the complete endpoint list, request schemas, response schemas, and authentication requirements, refer to the running OpenAPI documentation.

---

## Testing

SnapSort includes Flutter and backend testing workflows.

### Flutter Analysis

\`\`\`bash
flutter analyze
\`\`\`

### Flutter Tests

\`\`\`bash
flutter test
\`\`\`

### Flutter Debug Build

\`\`\`bash
flutter build apk --debug
\`\`\`

### Backend Tests

Run from the `backend` directory:

\`\`\`bash
python -m pytest -q
\`\`\`

Compile Python modules:

\`\`\`bash
python -m compileall -q app migrations tests scripts
\`\`\`

Check migration status:

\`\`\`bash
alembic current
alembic heads
\`\`\`

### Performance Benchmark

\`\`\`bash
python scripts/benchmark_health.py
\`\`\`

The health benchmark measures API health-endpoint latency under a local test workload. It does not represent a full production load test or an end-to-end AI matching benchmark.

---

## Deployment

SnapSort's backend API and background worker should run as separate services sharing the required database, Redis, storage, and AI configuration.

### Backend API Service

Start command:

\`\`\`bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
\`\`\`

### Background Worker Service

Start command:

\`\`\`bash
python -m app.worker
\`\`\`

The worker must be running for queued photo processing and matching jobs to complete.

### Android Release Build

Release builds should use a deployed HTTPS backend:

\`\`\`bash
flutter build apk --release --dart-define=SNAPSORT_API_BASE_URL=https://<your-api-host>
\`\`\`

Use a private signing keystore for production release builds. Store signing credentials securely and never commit them to GitHub.

---

## Security and Privacy

SnapSort processes personal photographs and facial representations. Privacy and access control are essential to the platform.

- Firebase authentication for user identity.
- Server-side verification of Firebase ID tokens.
- Backend authorization for protected operations.
- Event-scoped photo access.
- Event-specific consent for face matching.
- Consent revocation support.
- Private object storage for event photographs.
- Short-lived signed upload and download URLs.
- Verification of uploaded objects.
- Protected access to matching jobs and results.
- Server secrets kept out of mobile builds.
- Personal-gallery scanning performed locally on the device.
- No intended cross-event face searching.

Before public or commercial deployment, privacy policies, consent language, biometric-data requirements, retention periods, deletion processes, and applicable laws must be reviewed.

---

## Limitations

- Face matching may produce false positives and false negatives.
- Results depend on lighting, face angle, blur, occlusion, image resolution, and face visibility.
- AI processing requires the worker, Redis, database, model runtime, and storage services to be available.
- Initial AI setup may require downloading model files.
- Large events may require additional infrastructure and optimization.
- Matching accuracy and performance targets need validation against representative datasets.
- Local gallery scanning does not currently provide verified person-based grouping.
- Billing features depend on provider configuration and service availability.

---

## Business Model

SnapSort is designed around an **organizer-paid B2B2C business model** with pay-per-event pricing.

| Customer | Value |
|---|---|
| Event Organizer | Pays for event photo discovery, storage, and AI processing capacity. |
| Photographer | Uploads event photographs as part of the event workflow. |
| Attendee | Finds, views, favorites, downloads, and shares personal photos without a direct attendee fee. |

### Potential Pricing Plans

- **Free Trial:** Limited event capacity to experience SnapSort.
- **Standard:** Core event photo discovery features with defined quotas.
- **Pro:** Higher photo and attendee limits with expanded event capabilities.
- **Enterprise:** Customized plans for venues, organizations, schools, and recurring event businesses.

Pricing, quotas, and plan limits should be validated with real organizers and based on storage, processing, infrastructure, and operational costs.

Stripe Checkout and webhook integrations require valid provider configuration before billing can be enabled in production.

---

## Future Roadmap

Potential future improvements include:

- Improving face-matching accuracy.
- Optimizing similarity search for large galleries.
- Performance improvements for high-volume events.
- More comprehensive monitoring and operational analytics.
- Improved event retention and deletion workflows.
- Organizer analytics and event insights.
- Improved subscription and billing experience.
- Expanded automated test coverage.
- CI/CD integration.
- iOS application support.

Roadmap items are planned possibilities and are not necessarily implemented.

---

## Contributing

Contributions, bug reports, feature suggestions, and feedback are welcome.

1. Fork the repository.
2. Create a new feature branch.
3. Make your changes.
4. Run the relevant tests and checks.
5. Submit a pull request with a clear description.

For major features or architectural changes, open an issue first to discuss the proposed implementation.

---

## License

No license has currently been specified for this repository.

Until a license is added, permission to copy, modify, redistribute, or use this project should not be assumed.

---

<p align="center">
  Built to make event memories easier to find.
</p>
