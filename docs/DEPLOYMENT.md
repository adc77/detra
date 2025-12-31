# VertiGuard Deployment Guide

**IMPORTANT**: VertiGuard is a **library**, not a hosted service. This guide covers:
1. How to deploy the **demo application** (for challenge judges)
2. How users will **integrate** VertiGuard into their own apps

## 🎯 What Gets Deployed?

For the Datadog Challenge, we deploy the **demo application** (`examples/legal_analyzer/`), which **uses** VertiGuard to show judges how it works.

VertiGuard itself is a pip-installable library that users integrate into their own applications.

## Prerequisites

- Datadog account with API key and App key
- Google API key (for Gemini)
- Docker installed (for containerized deployment)

## For Challenge: Deploy Demo Application

The demo app (`examples/legal_analyzer/`) showcases VertiGuard's capabilities.

### Deploy to Railway

```bash
# Navigate to demo app
cd examples/legal_analyzer/

# Initialize Railway
railway login
railway init

# Set environment variables
railway variables set DD_API_KEY=your_key
railway variables set DD_APP_KEY=your_key
railway variables set DD_SITE=datadoghq.com
railway variables set GOOGLE_API_KEY=your_key

# Deploy
railway up

# Get URL
railway domain
# This URL goes in your challenge submission
```

### Deploy to Render

1. Push to GitHub
2. Create New Web Service on Render
3. Connect your repo
4. Point to `examples/legal_analyzer/app.py`
5. Set environment variables in dashboard
6. Deploy automatically

## For Users: Integrate VertiGuard

After the challenge, users install VertiGuard into THEIR applications:

```bash
# User installs library
pip install vertiguard

# User integrates into their app
# (See examples/ directory)
```

## Quick Start - Local Testing

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Set Environment Variables

```bash
export DD_API_KEY=your_datadog_api_key
export DD_APP_KEY=your_datadog_app_key
export DD_SITE=datadoghq.com
export GOOGLE_API_KEY=your_google_api_key
export SLACK_WEBHOOK_URL=your_slack_webhook  # Optional
```

### 3. Run Example Application

```bash
python examples/legal_analyzer/app.py
```

### 4. Generate Traffic

```bash
python scripts/traffic_generator.py --requests 50 --delay 2
```

### 5. Export Datadog Configurations

```bash
python scripts/export_datadog_configs.py
```

## Docker Deployment

### Build and Run

```bash
# Build image
docker build -t vertiguard-demo .

# Run container
docker run -d \
  -e DD_API_KEY=$DD_API_KEY \
  -e DD_APP_KEY=$DD_APP_KEY \
  -e DD_SITE=$DD_SITE \
  -e GOOGLE_API_KEY=$GOOGLE_API_KEY \
  --name vertiguard \
  vertiguard-demo
```

### Using Docker Compose

```bash
# Create .env file with your credentials
cat > .env <<EOF
DD_API_KEY=your_datadog_api_key
DD_APP_KEY=your_datadog_app_key
DD_SITE=datadoghq.com
GOOGLE_API_KEY=your_google_api_key
SLACK_WEBHOOK_URL=your_slack_webhook
EOF

# Start services
docker-compose up -d

# Run traffic generator
docker-compose --profile testing up traffic-generator
```

## Cloud Deployment

### Railway

1. **Create Railway Project**
   ```bash
   railway login
   railway init
   ```

2. **Set Environment Variables**
   ```bash
   railway variables set DD_API_KEY=your_key
   railway variables set DD_APP_KEY=your_key
   railway variables set DD_SITE=datadoghq.com
   railway variables set GOOGLE_API_KEY=your_key
   ```

3. **Deploy**
   ```bash
   railway up
   ```

4. **Get URL**
   ```bash
   railway domain
   ```

### Render

1. **Create New Web Service**
   - Connect your GitHub repository
   - Render will auto-detect the `Dockerfile`

2. **Configure Environment Variables**
   - Add `DD_API_KEY`, `DD_APP_KEY`, `DD_SITE`, `GOOGLE_API_KEY`
   - Set in Dashboard → Environment

3. **Deploy**
   - Render deploys automatically on git push

### Google Cloud Run

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT_ID/vertiguard

# Deploy to Cloud Run
gcloud run deploy vertiguard \
  --image gcr.io/PROJECT_ID/vertiguard \
  --platform managed \
  --region us-central1 \
  --set-env-vars DD_API_KEY=$DD_API_KEY,DD_APP_KEY=$DD_APP_KEY,DD_SITE=$DD_SITE,GOOGLE_API_KEY=$GOOGLE_API_KEY
```

## Testing the Deployment

### 1. Run E2E Tests

```bash
python scripts/test_e2e.py
```

### 2. Generate Test Traffic

```bash
# Generate 100 requests over 5 minutes
python scripts/traffic_generator.py --requests 100 --delay 3
```

### 3. Verify in Datadog

1. **Check LLM Observability**
   - Navigate to: APM → LLM Observability
   - Look for traces tagged with `service:legal-analyzer`

2. **View Dashboard**
   - Navigate to: Dashboards
   - Find: "VertiGuard: LLM Observability"

3. **Check Monitors**
   - Navigate to: Monitors → Manage Monitors
   - Filter by `source:vertiguard`

4. **View Incidents**
   - Navigate to: Incidents
   - Look for any created by VertiGuard

## Datadog Configuration Export

After running your application and creating monitors/dashboards:

```bash
python scripts/export_datadog_configs.py --output-dir datadog_exports
```

This creates:
- `monitors_*.json` - All VertiGuard monitors
- `dashboards_*.json` - All dashboards
- `slos_*.json` - SLO definitions (if any)
- `export_summary.json` - Summary of exports
- `README.md` - Documentation

## Troubleshooting

### "VertiGuard not initialized" Error

Ensure you call `vertiguard.init()` before using decorators:

```python
import vertiguard

vg = vertiguard.init("vertiguard.yaml")

@vg.trace("my_function")  # Now decorators will work
async def my_function():
    pass
```

### Datadog Metrics Not Appearing

1. Verify API keys are correct
2. Check `DD_SITE` matches your Datadog account
3. Ensure network connectivity to Datadog
4. Check application logs for errors

### Evaluation Not Running

1. Verify `GOOGLE_API_KEY` is set
2. Check node configuration exists in `vertiguard.yaml`
3. Ensure `evaluate=True` in decorator (default)

### Docker Build Fails

1. Ensure all dependencies are in `pyproject.toml`
2. Check Docker has enough memory (4GB+ recommended)
3. Try `docker system prune` to clean up

## Production Considerations

### Security

- **Never commit API keys** - Use environment variables
- **Rotate keys regularly** - Especially after public demos
- **Use secrets management** - Railway/Render secret management, or AWS Secrets Manager

### Scaling

- **Rate limiting** - Be mindful of Gemini API limits
- **Caching** - Enable evaluation result caching for repeated inputs
- **Async processing** - VertiGuard is built async-first for performance

### Monitoring

- **Set up alerts** - Configure Slack/PagerDuty for critical issues
- **Dashboard monitoring** - Regularly check adherence trends
- **Cost tracking** - Monitor token usage metrics

## Support

- Issues: [GitHub Issues](https://github.com/your-org/verti-guard/issues)
- Documentation: [README.md](README.md)
- Examples: [examples/](examples/)
