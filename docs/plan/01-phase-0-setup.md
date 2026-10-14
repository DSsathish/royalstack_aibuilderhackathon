# Phase 0: Project Setup

Goal: a deployable skeleton on Google Cloud by the end of 14 Oct. Every later phase assumes this is done.
Owner: product / infra. Estimated time: 3 to 4 hours.

## 0.1 Team and accounts

1. Confirm team of 2 to 4 on the Hack2skill portal before team formation closes (14 Oct).
2. One Google account owns the Google Cloud project. Add teammates as `roles/editor`.
3. One GitHub account creates the public repo. Add teammates as collaborators.
4. Create a shared `.env.example` and a private channel (WhatsApp/Discord) for secrets. Never commit secrets.

## 0.2 Google Cloud project

```bash
export PROJECT_ID=aibuildercup-retail-2026     # change if taken
export REGION=asia-south1                       # Mumbai; use asia-southeast1 if Gemini features need it

gcloud projects create $PROJECT_ID --name="AI Builder Cup Retail"
gcloud config set project $PROJECT_ID
# Link billing in the console: Billing > Link a billing account

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  pubsub.googleapis.com \
  firebase.googleapis.com \
  identitytoolkit.googleapis.com \
  cloudresourcemanager.googleapis.com
```

4. Create Firestore database in native mode:

```bash
gcloud firestore databases create --location=$REGION
```

5. Create Artifact Registry repo for container images:

```bash
gcloud artifacts repositories create app --repository-format=docker --location=$REGION
```

6. Create BigQuery dataset:

```bash
bq --location=$REGION mk --dataset $PROJECT_ID:retail
```

## 0.3 Firebase

1. Go to console.firebase.google.com, "Add project", pick the existing Google Cloud project.
2. Enable Authentication providers: Anonymous, Google, Phone (phone needs test numbers for the demo; add 2 to 3 test numbers under Auth > Sign-in method > Phone > test numbers).
3. Enable Hosting. Install CLI:

```bash
npm i -g firebase-tools
firebase login
firebase init hosting   # choose frontend/out or Next.js framework support
```

4. Register a Web app, copy the Firebase config object into `frontend/.env.local` as `NEXT_PUBLIC_FIREBASE_*`.

## 0.4 Gemini access

Choose one and record it in the overview open items:

- **Vertex AI (recommended):** no key needed on Cloud Run, uses the service account. Locally, `gcloud auth application-default login`. Set `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`.
- **AI Studio key:** create at aistudio.google.com, store in Secret Manager as `GEMINI_API_KEY`.

Check the current model list in AI Studio or Vertex Model Garden on build day and put the IDs in config:

```
GEMINI_FLASH_MODEL=gemini-2.5-flash      # or newer stable Flash
GEMINI_PRO_MODEL=gemini-2.5-pro          # or newer stable Pro
```

## 0.5 Service accounts and secrets

```bash
gcloud iam service-accounts create retail-api --display-name="Retail API runtime"
SA=retail-api@$PROJECT_ID.iam.gserviceaccount.com
for role in roles/datastore.user roles/bigquery.dataEditor roles/bigquery.jobUser \
            roles/aiplatform.user roles/secretmanager.secretAccessor roles/pubsub.publisher; do
  gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA" --role="$role"
done

# secrets
printf "%s" "<razorpay-test-key-secret>" | gcloud secrets create RAZORPAY_KEY_SECRET --data-file=-
printf "%s" "<random-64-bytes>"          | gcloud secrets create QR_SESSION_SIGNING_KEY --data-file=-
# add GEMINI_API_KEY, TWILIO_AUTH_TOKEN, SHOPIFY_TOKEN later as needed
```

## 0.6 Repository skeleton

```bash
mkdir aibuildercup-retail && cd aibuildercup-retail
git init
mkdir -p backend/app/{agent,connectors,domain,services,api} backend/tests frontend infra/{scripts,seed} .github/workflows docs
```

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn[standard] google-adk google-genai google-cloud-firestore \
            google-cloud-bigquery google-cloud-secret-manager pydantic-settings \
            python-multipart httpx pytest pytest-asyncio
pip freeze > requirements.txt
```

Minimal `app/main.py`:

```python
from fastapi import FastAPI
app = FastAPI(title="Retail Agent API")

@app.get("/healthz")
def healthz():
    return {"ok": True}
```

`Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV PORT=8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Frontend:

```bash
cd ../frontend
npx create-next-app@latest . --ts --app --tailwind --eslint --src-dir=false
npm i firebase @zxing/browser qrcode zustand
```

## 0.7 First deploy

Backend to Cloud Run:

```bash
cd backend
gcloud run deploy retail-api \
  --source . --region $REGION --service-account $SA \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION \
  --set-secrets QR_SESSION_SIGNING_KEY=QR_SESSION_SIGNING_KEY:latest
```

Record the service URL. Frontend to Firebase Hosting:

```bash
cd ../frontend
firebase deploy --only hosting
```

## 0.8 CI/CD

`.github/workflows/deploy.yml` (uses Workload Identity Federation or a JSON key stored as a GitHub secret; JSON key is acceptable for a 4-day hackathon):

```yaml
name: deploy
on:
  push:
    branches: [main]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with: { credentials_json: "${{ secrets.GCP_SA_KEY }}" }
      - uses: google-github-actions/setup-gcloud@v2
      - run: pip install -r backend/requirements.txt && pytest backend/tests -q
      - run: gcloud run deploy retail-api --source backend --region ${{ vars.REGION }} --quiet
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: cd frontend && npm ci && npm run build
      - uses: FirebaseExtended/action-hosting-deploy@v0
        with:
          repoToken: "${{ secrets.GITHUB_TOKEN }}"
          firebaseServiceAccount: "${{ secrets.FIREBASE_SA_KEY }}"
          channelId: live
          projectId: ${{ vars.PROJECT_ID }}
```

## 0.9 Local development

- `backend`: `uvicorn app.main:app --reload --port 8080`
- `frontend`: `npm run dev`, with `NEXT_PUBLIC_API_URL=http://localhost:8080`
- Firestore emulator optional: `firebase emulators:start --only firestore,auth`. Prefer the real dev Firestore to save time.

## Acceptance criteria

- [ ] `https://<cloud-run-url>/healthz` returns `{"ok": true}`
- [ ] Firebase Hosting URL serves the Next.js placeholder page
- [ ] Push to `main` deploys both automatically
- [ ] Teammates can run both locally with `.env` from the shared channel
- [ ] Project ID, URLs, and model IDs written into `00-overview.md` open items

## Risks

- Billing not linked: Cloud Run deploy fails. Do this first.
- Region mismatch between Firestore, BigQuery, and Vertex: pick one region and use it everywhere. If a Gemini feature is unavailable in asia-south1, use `global` or `us-central1` for Vertex only.
