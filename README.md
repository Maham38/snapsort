# SnapSort

SnapSort is a Flutter Android application for finding personal photographs in
event galleries.

## Phase 2: authentication

The app now includes Firebase Authentication integration for:

- Email/password registration and sign-in.
- Password reset email requests.
- Firebase auth session persistence through `authStateChanges`.
- Firestore user profiles with a selected `role`.
- Backend user roles synchronized through the authenticated `/api/v1/me/role`
  endpoint.
- Explicit sign-out and authentication error states.

No Firebase credentials are committed to this repository.

## Local Firebase setup

1. Install the FlutterFire CLI:

   ```powershell
   dart pub global activate flutterfire_cli
   ```

2. Log in to Firebase and configure the Android app:

   ```powershell
   firebase login
   flutterfire configure
   ```

   Select the Firebase project and Android package configured by the CLI. This
   generates the local `firebase_options.dart` and platform configuration
   files. These files are environment-specific and should not be committed if
   they contain project credentials.

3. In the Firebase console, enable **Authentication > Sign-in method >
   Email/Password** and create the Firestore database.

4. Apply rules so users can only write their own profile document. A production
   deployment must also add server-side authorization rules before event data
   is introduced.

Without Firebase configuration, the app still launches and displays the Phase
1 onboarding UI, but authentication actions show an explicit configuration
error instead of using fake accounts.

## Phase 3: FastAPI backend

The backend is in [backend/](backend/) and provides:

- FastAPI REST API with OpenAPI documentation.
- Firebase ID-token verification on protected routes.
- Role-based authorization for organizer event creation.
- PostgreSQL/SQLAlchemy models for users, events, participants,
  photographer assignments, photos, embeddings, matching jobs, favorites, and
  consent records.
- Alembic migration `0001_initial_schema`.
- pgvector `Vector(512)` storage for face embeddings.
- Explicit health, authentication, role, and event endpoints.

Run locally:

```powershell
cd backend
python -m pip install -e ".[test]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The PostgreSQL `vector` extension must be enabled by the database owner. The
backend does not create schemas automatically; migrations are the only schema
change mechanism. Firebase credentials are loaded from environment
configuration and are never stored in the repository.

## Phase 4: organizer event management

Organizer functionality now includes:

- Authenticated event listing.
- Event creation with collision-safe unique codes.
- Event editing with ownership checks.
- Event deletion with confirmation and related-record protection.
- Event-code display and QR generation in the Flutter organizer dashboard.

The Flutter API client uses the Firebase ID token as a bearer token. Android
emulators call the local API through `http://10.0.2.2:8000`. A physical device
cannot use `10.0.2.2`; use the computer's Wi-Fi/LAN address and keep both
devices on the same network:

```powershell
flutter run --dart-define=SNAPSORT_API_BASE_URL=http://<computer-lan-ip>:8000
```

For a USB-connected Android device, port forwarding avoids LAN configuration:

```powershell
adb reverse tcp:8000 tcp:8000
flutter run --dart-define=SNAPSORT_API_BASE_URL=http://127.0.0.1:8000
```

If the physical device still cannot connect, allow inbound TCP port `8000`
through Windows Firewall for the active private network. Release builds must
use a deployed HTTPS API instead.

## Phase 5: photographer uploads

Photographer functionality now includes:

- Photographer event-code joining and organizer assignment of photographer
  Firebase users to events.

  The Photos tab is event-based for every role. Organizer and photographer
  photos are grouped by the event they uploaded to. Attendee matching results
  are saved with the event ID and event name, shown under that event, and each
  event provides a Download all action. Matched photos are saved to the
  device's `Pictures/SnapSort` album.
- Assigned-event listing for photographers.
- Multiple image selection for JPG, JPEG, PNG, and WebP files.
- Per-file upload progress, retry state, and upload history metadata.
- Short-lived Supabase Storage signed upload URLs.
- Server-side upload authorization and object-existence verification.

Configure Supabase Storage before uploading real files:

```env
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=<server-only-secret-key>
SUPABASE_BUCKET_NAME=event-photos
SUPABASE_SIGNED_URL_TTL_SECONDS=900
```

Create a private `event-photos` bucket in Supabase Storage. Keep the
secret key only in `backend/.env`; never put it in Flutter or commit it.
The backend never receives the file bytes. It creates a database photo record,
the mobile client uploads directly to Supabase Storage using the short-lived
signed URL, and the completion endpoint verifies that the object exists before
leaving the photo ready for processing.

## Verify

```powershell
flutter analyze
flutter test
flutter build apk --debug
```

Backend verification:

```powershell
cd backend
python -m pytest -q
python -m compileall -q app migrations tests
alembic heads
```

## Phase 6: AI processing and event-scoped matching

Phase 6 adds server-side face processing without simulated embeddings:

- Photo processing jobs are queued in Redis after upload completion.
- The worker uses InsightFace with ONNX Runtime to create 512-dimensional
  embeddings.
- Embeddings are stored in PostgreSQL with an IVFFlat vector index.
- Attendee face-matching requires event membership and active explicit consent.
- Matching jobs and results are scoped to one event and one attendee.
- Consent can be revoked through the API.

Install the optional AI runtime and run the worker in a separate process:

```powershell
cd backend
python -m pip install -e ".[ai,test]"
alembic upgrade head
python -m app.worker
```

Redis must be running at `REDIS_URL`. The first InsightFace model startup may
download model assets; configure `AI_MODEL_ROOT` for a controlled model cache.
If the AI runtime, model, Redis queue, or private Supabase object is unavailable,
the job is marked failed or the API returns an explicit service error. No
random or fallback face vectors are generated.

Phase 6 API routes:

- `POST /api/v1/events/{event_id}/consent`
- `DELETE /api/v1/events/{event_id}/consent/{consent_type}`
- `POST /api/v1/events/{event_id}/matching-jobs`
- `GET /api/v1/matching-jobs/{job_id}`
- `GET /api/v1/matching-jobs/{job_id}/results`

## Phase 7: attendee matching

Attendees can now:

- Join an active event with its organizer-provided event code.
- View joined events.
- Grant explicit face-matching consent for an event.
- Select and securely upload one selfie to private Supabase Storage.
- Submit an event-scoped matching job and observe its progress.
- View personalized results through short-lived signed image URLs.

The selfie object key is generated by the backend and is checked against the
authenticated attendee before a matching job is accepted. Matching results
remain scoped to the job's event and attendee. The Flutter attendee flow is
available from the attendee dashboard's **Join an event** action.

## Phase 8: gallery, favorites, downloads, and sharing

Completed matching photos are now exposed through an attendee-authorized
gallery endpoint. Each image uses a short-lived signed Supabase download URL.
The backend verifies that the attendee owns a completed matching result before
returning a gallery image or changing its favorite state.

The Flutter gallery supports:

- Lazy network image loading in a two-column grid.
- Favorite and remove-favorite actions.
- Downloading a photo into the app's private documents directory.
- Sharing a signed photo URL through the Android share sheet.

Favorites and gallery access never accept an arbitrary storage key from the
mobile client.

## Phase 9: on-device gallery organization

The optional personal-gallery flow is local to the Android device:

- Requests photo-library permission before scanning.
- Scans up to 100 device images without uploading them.
- Deduplicates the current scan by Android asset ID.
- Lets the user exclude individual photos.
- Saves selected photos to `Pictures/SnapSort`.
- Skips files already saved by SnapSort.
- Provides a switch to disable scanning from the screen.

Personal-gallery scanning is never sent to the FastAPI backend or used for
event matching. Person-based grouping is intentionally not shown yet because
no verified on-device face model has been integrated; the app does not
simulate groups.

## Phase 10: security and privacy hardening

- Users can select organizer, photographer, or attendee during profile setup
  and can update their role without administrator approval.
- Consent is unique per user, event, and consent type. Revocation marks every
  legacy duplicate inactive, and migration `0003_security_hardening` removes
  duplicates before enforcing the unique index.
- Release Flutter builds reject missing or non-HTTPS API URLs. Configure the
  production endpoint explicitly:

```powershell
flutter build apk --release `
  --dart-define=SNAPSORT_API_BASE_URL=https://api.example.com
```

The local `http://10.0.2.2:8000` endpoint remains available only for debug
development. Never use it in a production build.

## Phase 12: Android release

Release builds never use the Android debug key. Provide a private keystore
through environment variables before creating an APK or AAB:

```powershell
$env:SNAPSORT_RELEASE_STORE_FILE="D:\secure\snapsort-upload.jks"
$env:SNAPSORT_RELEASE_STORE_PASSWORD="<keystore-password>"
$env:SNAPSORT_RELEASE_KEY_ALIAS="snapsort"
$env:SNAPSORT_RELEASE_KEY_PASSWORD="<key-password>"

flutter build apk --release `
  --dart-define=SNAPSORT_API_BASE_URL=https://api.example.com

flutter build appbundle --release `
  --dart-define=SNAPSORT_API_BASE_URL=https://api.example.com
```

Keep the keystore and passwords outside the repository and CI logs. The
release output is generated under `build/app/outputs/`; do not commit it.
The current Android application ID is `com.example.snapsort`; change it only
after registering the new package with Firebase and updating the Android
Firebase configuration.

## Phase 11: testing and performance

Automated validation currently covers:

- FastAPI health and authentication boundaries.
- Protected event, upload, gallery, favorite, and matching routes.
- OpenAPI exposure of the Phase 6-8 API contract.
- Flutter onboarding and form validation.
- Python compilation and Alembic migration state.

Run the suites:

```powershell
flutter analyze
flutter test
cd backend
python -m pytest -q
python -m compileall -q app migrations tests scripts
alembic current
```

Measure local non-ML API latency:

```powershell
cd backend
python scripts/benchmark_health.py
```

The benchmark reports median, p95, and maximum latency for 100 local health
requests. It is not a production load test. The required 300 ms p95 target
must be measured separately against the deployed API under documented load.
The under-three-second face-matching target must be measured after event
indexing on a representative 5,000-photo dataset; upload and initial
embedding generation are excluded from that target.

Run the background worker while testing photo processing and face matching:

```powershell
cd backend
python -m app.worker
```

The deployed API and worker must run as separate services that share the same
`DATABASE_URL`, `REDIS_URL`, Supabase settings, and AI model settings. The
backend Docker image starts the API by default. For a Railway worker service,
use the same backend image with this start command:

```powershell
python -m app.worker
```

If the worker service is not running, matching jobs are accepted by the API but
remain pending, and the attendee app stops waiting after five minutes with an
explicit service-unavailable message.

Photographers can join an active event from the app using the event code, then
select and upload multiple JPG, JPEG, PNG, or WebP files. The organizer no
longer needs to create a photographer assignment first.

The Firebase service is in
[lib/services/auth_service.dart](lib/services/auth_service.dart). UI and
navigation remain in [lib/main.dart](lib/main.dart).

## Business model

SnapSort should launch as a **B2B2C organizer-paid service**:

- **Primary customer:** event organizers, wedding planners, schools, and
  photographers who need to deliver large event galleries.
- **Free users:** attendees can join an event, give explicit matching consent,
  find their photos, favorite them, download them, and share them.
- **Photographers:** photographers can upload to assigned events at no extra
  charge, which keeps the supply of event photos healthy.

### Launch offer: pay per event

Charge the organizer for each event instead of requiring a subscription before
the product has proven repeat usage. A practical initial structure is:

1. **Free trial event:** one small event with a photo and attendee limit.
2. **Standard event:** a fixed fee based on storage, photo volume, and matching
   usage.
3. **Pro event:** a higher limit plus branded galleries, longer retention,
   analytics, and priority processing.
4. **Enterprise:** negotiated pricing for venues, schools, and agencies that
   run recurring events.

Prices should be validated with 5-10 organizers before being treated as
final. Keep AI matching and storage quotas explicit so an unusually large event
cannot make a paid event unprofitable.

### Why this model fits SnapSort

- The organizer receives the clearest business value: less manual gallery
  delivery and a better attendee experience.
- Event-based billing matches the existing `Event` boundary and naturally
  covers variable storage, image processing, and signed-download costs.
- Attendee access remains frictionless, improving event adoption and reducing
  support requests.
- Privacy and consent remain product differentiators; attendee data and face
  matching should never be monetized through advertising or data resale.

### Growth path

After measuring repeat organizer usage, evolve into a hybrid model: free small
events, paid larger events, and an optional organizer subscription with bundled
monthly event credits. Add billing only after tracking event volume, storage,
matching-job cost, conversion from trial to paid, repeat organizer rate, and
revenue per event.

### Billing setup

Billing is implemented with Stripe Checkout and is disabled until the backend
has all of these environment variables:

```env
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_SUCCESS_URL=https://your-app.example/billing/success
STRIPE_CANCEL_URL=https://your-app.example/billing/cancel
```

Keep the values only in `backend/.env` or the deployment secret manager. Never
put Stripe keys in Flutter or source control. Apply the billing schema before
starting the API:

```powershell
cd backend
Copy-Item .env.example .env
alembic upgrade head
```

Configure the Stripe webhook endpoint as
`POST https://<api-host>/api/v1/billing/webhook` and subscribe it to
`checkout.session.completed` (and failed/expired checkout events if those are
enabled by the provider account). Stripe signatures are verified server-side;
client-reported payment status is never accepted.

The seeded plan prices and limits in migration `0004_billing` are placeholders.
Change them in the database before launch and validate them with organizers.
Enterprise activation is intentionally a manual/admin workflow and is not
implemented as a public checkout option. Run
`python scripts/expire_billing.py` periodically to expire plans and flag data
for retention review; the command never deletes data automatically.

## Firestore profile rules

The app stores only the signed-in user's profile in Firestore. Deploy the
least-privilege rules after selecting the `snapsort-6924e` Firebase project:

```powershell
firebase login
firebase use snapsort-6924e
firebase deploy --only firestore:rules
```

The rules allow users to read and create only their own profile. Initial
profile creation may omit the role, and users may assign or change their role
to `organizer`, `photographer`, or `attendee`. Backend endpoints still enforce
the selected role for protected organizer and photographer operations.
