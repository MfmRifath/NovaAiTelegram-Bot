#!/bin/bash
# Deploy NovaAI Telegram Bot to Google Cloud Run

set -e  # Exit on error

# Configuration
PROJECT_ID="novascience-31488"
REGION="us-central1"
SERVICE_NAME="novaai-telegram-bot"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying NovaAI Telegram Bot to Google Cloud Run"
echo "=================================================="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Load environment variables from .env
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create a .env file with your configuration."
    exit 1
fi

echo "📦 Step 1: Building Docker image for linux/amd64..."
docker build --platform linux/amd64 -t ${IMAGE_NAME} .

echo ""
echo "☁️  Step 2: Pushing image to Google Container Registry..."
docker push ${IMAGE_NAME}

echo ""
echo "🚢 Step 3: Deploying to Cloud Run..."

# Extract environment variables from .env file (handle values with spaces properly)
TELEGRAM_BOT_TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d'=' -f2-)
OPENAI_API_KEY=$(grep '^OPENAI_API_KEY=' .env | cut -d'=' -f2-)
CLAUDE_API_KEY=$(grep '^CLAUDE_API_KEY=' .env | cut -d'=' -f2-)
GEMINI_API_KEY=$(grep '^GEMINI_API_KEY=' .env | cut -d'=' -f2-)
OWNER_USER_ID=$(grep '^OWNER_USER_ID=' .env | cut -d'=' -f2-)

gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --min-instances 1 \
    --max-instances 1 \
    --port 8080 \
    --set-env-vars "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN},OPENAI_API_KEY=${OPENAI_API_KEY},CLAUDE_API_KEY=${CLAUDE_API_KEY},GEMINI_API_KEY=${GEMINI_API_KEY},OWNER_USER_ID=${OWNER_USER_ID}"

echo ""
echo "✅ Deployment completed successfully!"
echo ""

echo "🧹 Cleaning up old revisions..."
# Keep only the latest revision, delete all others to prevent conflicts
gcloud run revisions list --service=${SERVICE_NAME} --region=${REGION} --format="value(metadata.name)" | tail -n +2 | while read revision; do
    echo "  Deleting old revision: $revision"
    gcloud run revisions delete $revision --region=${REGION} --quiet 2>/dev/null || true
done

echo ""
echo "📊 Service Information:"
gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format="value(status.url)"
echo ""
echo "💡 Useful commands:"
echo "  View logs: gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}' --limit 50 --format=json"
echo "  Check status: gcloud run services describe ${SERVICE_NAME} --region ${REGION}"
echo "  Delete service: gcloud run services delete ${SERVICE_NAME} --region ${REGION}"
echo ""
echo "🎉 Your bot should now be running!"
