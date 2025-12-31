# Datadog Challenge Submission Checklist

## ✅ Hard Requirements

### 1. Application with Vertex AI/Gemini
- [x] Application uses Gemini API
- [x] LLM functionality implemented (entity extraction, summarization, Q&A)
- [x] Properly handles LLM errors

### 2. Datadog Telemetry
- [x] LLM Observability (ddtrace LLMObs)
- [x] APM tracing
- [x] Custom metrics
- [x] Logs with structured context
- [x] Events for flags and incidents

### 3. Detection Rules (3+)
- [x] **Rule 1**: Adherence Score Warning (< 0.85)
- [x] **Rule 2**: Adherence Score Critical (< 0.70)
- [x] **Rule 3**: PII/PHI Detection (security_issues > 0)
- [x] **Rule 4**: High Latency (> 5000ms)
- [x] **Rule 5**: Flag Rate Warning (> 10%)
- [x] **Rule 6**: Error Rate (> 5%)
- [x] **Rule 7**: Security Issues (any detected)
- [x] **Rule 8**: Token Usage Warning

### 4. Actionable Records in Datadog
- [x] Incident creation on critical issues
- [x] Case management for tracking
- [x] Contextual information included
- [x] Runbook/next steps provided

### 5. Dashboard
- [x] Application health metrics
- [x] SLO status
- [x] Detection rule status
- [x] Actionable items widget
- [x] LLM-specific metrics (adherence, tokens, etc.)

### 6. Repository
- [x] OSI-approved license (MIT)
- [x] README with deployment instructions
- [x] Instrumented application code
- [x] Traffic generator script
- [x] Datadog config exports (JSON)

### 7. Hosted Application
- [ ] **TODO**: Deploy to Railway/Render/Cloud Run
- [ ] **TODO**: Provide public URL in README

### 8. Video Walkthrough (3 min)
- [ ] **TODO**: Record video showing:
  - [ ] Observability strategy explanation
  - [ ] Dashboard walkthrough
  - [ ] Detection rules triggering
  - [ ] Incident creation flow
  - [ ] Innovation highlights

## 📦 Submission Contents

### Repository Files

```
verti-guard/
├── LICENSE                          ✅ MIT License
├── README.md                        ✅ Complete documentation
├── DEPLOYMENT.md                    ✅ Deployment guide
├── pyproject.toml                   ✅ Dependencies
├── Dockerfile                       ✅ Container config
├── docker-compose.yml               ✅ Multi-service setup
├── railway.json                     ✅ Railway config
├── render.yaml                      ✅ Render config
├── src/vertiguard/                  ✅ Core library
│   ├── client.py                    ✅ Main client
│   ├── decorators/                  ✅ Trace decorators
│   ├── evaluation/                  ✅ LLM evaluation
│   ├── security/                    ✅ Security scanners
│   ├── telemetry/                   ✅ Datadog integration
│   ├── detection/                   ✅ Monitors & rules
│   ├── actions/                     ✅ Incidents & alerts
│   ├── dashboard/                   ✅ Dashboard builder
│   └── optimization/                ✅ DSPy & root cause
├── examples/legal_analyzer/         ✅ Demo application
│   ├── app.py                       ✅ Example code
│   └── vertiguard.yaml              ✅ Configuration
├── scripts/                         ✅ Utility scripts
│   ├── traffic_generator.py         ✅ Traffic generator
│   ├── export_datadog_configs.py    ✅ Config exporter
│   └── test_e2e.py                  ✅ E2E tests
├── tests/                           ✅ Unit tests
└── datadog_exports/                 ⏳ To be generated
    ├── monitors_*.json              ⏳ Export after setup
    ├── dashboards_*.json            ⏳ Export after setup
    └── export_summary.json          ⏳ Export after setup
```

## 🚀 Pre-Submission Steps

### Step 1: Local Testing

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Set environment variables
export DD_API_KEY=your_key
export DD_APP_KEY=your_key
export DD_SITE=datadoghq.com
export GOOGLE_API_KEY=your_key

# 3. Run E2E tests
python scripts/test_e2e.py

# 4. Run example app
python examples/legal_analyzer/app.py

# 5. Generate traffic
python scripts/traffic_generator.py --requests 50
```

### Step 2: Datadog Setup

```bash
# 1. Create monitors and dashboard
# (Run example app first, it will auto-create)

# 2. Verify in Datadog UI
# - Check LLM Observability
# - View dashboard
# - Confirm monitors exist

# 3. Export configurations
python scripts/export_datadog_configs.py
```

### Step 3: Deployment

```bash
# Option A: Railway
railway login
railway init
railway variables set DD_API_KEY=...
railway up
railway domain  # Get public URL

# Option B: Render
# Push to GitHub, connect via Render dashboard

# Option C: Docker local
docker-compose up -d
```

### Step 4: Evidence Collection

1. **Screenshot Dashboard**
   - Full dashboard view with live data
   - Save as `docs/dashboard_screenshot.png`

2. **Screenshot Incident**
   - Triggered incident with details
   - Save as `docs/incident_example.png`

3. **Screenshot Monitors**
   - List of monitors
   - Save as `docs/monitors_screenshot.png`

### Step 5: Video Recording

**Script (3 minutes)**:

```
[0:00-0:30] Introduction & Problem Statement
- Traditional LLM monitoring misses semantic issues
- VertiGuard provides behavior-based monitoring
- Show architecture diagram

[0:30-1:30] Live Demo
- Show Datadog dashboard with live data
- Trigger detection rule (run traffic generator)
- Show incident creation
- Highlight contextual information

[1:30-2:30] Innovation Deep Dive
- Semantic boundary detection
- DSPy prompt optimization
- Root cause analysis with LLM
- Multi-layer evaluation pipeline

[2:30-3:00] Results & Challenges
- Show metrics on detection accuracy
- Discuss Vertex AI integration
- Future enhancements
```

**Tools**:
- Loom, OBS Studio, or QuickTime
- Upload to YouTube (unlisted)

## 📤 Final Submission

### What to Submit

1. **GitHub Repository URL**
   - Public repository
   - All code and configs committed
   - datadog_exports/ included

2. **Hosted Application URL**
   - Railway/Render/Cloud Run URL
   - Add to README.md

3. **Video URL**
   - YouTube unlisted link
   - Add to README.md

4. **Datadog Organization Name**
   - Add to README.md: `Datadog Org: your-org-name`

### README Updates

Ensure README.md contains:

```markdown
# VertiGuard

[Description...]

## Datadog Challenge Submission

- **Hosted Application**: https://your-app.railway.app
- **Video Walkthrough**: https://youtu.be/your-video-id
- **Datadog Organization**: your-datadog-org
- **Dashboard**: [Link to dashboard]

## Detection Rules Implemented

1. **Adherence Score Warning** - Alerts when < 0.85
2. **Adherence Score Critical** - Critical alert when < 0.70
3. **PII/PHI Detection** - Immediate alert on exposure
4. **High Latency** - Warns when > 5000ms
5. **Flag Rate** - Alerts on high failure rate
6. **Security Issues** - Critical security violations
7. **Error Rate** - Application error monitoring
8. **Token Usage** - Cost tracking alerts

[Rest of README...]
```

## ✨ Innovation Highlights

Key differentiators to emphasize in video:

1. **Semantic Monitoring**
   - Goes beyond metrics to understand *meaning*
   - Detects hallucinations and semantic drift

2. **Behavior-Based Evaluation**
   - Define expected/unexpected behaviors in config
   - Automatic adherence scoring with Gemini

3. **Intelligent Optimization**
   - DSPy-powered prompt improvement
   - LLM-based root cause analysis with fix suggestions

4. **Drop-in Library**
   - Simple decorator-based integration
   - Works with any LLM application

5. **Context-Rich Incidents**
   - Every alert includes full context
   - Actionable remediation steps
   - Trace ID correlation

## 🎯 Success Criteria

Before submitting, verify:

- [ ] All hard requirements met
- [ ] Application deployed and accessible
- [ ] Datadog dashboard showing live data
- [ ] At least 3 detection rules configured
- [ ] Incidents created automatically
- [ ] Traffic generator demonstrates all patterns
- [ ] Video clearly explains strategy
- [ ] Repository complete with exports
- [ ] README has all required information

## 📝 Notes

**Datadog Site**: Ensure you're using the correct site (datadoghq.com, datadoghq.eu, etc.)

**Vertex AI vs Gemini**: Using Gemini API is acceptable per challenge rules ("Vertex AI or Gemini")

**Token Costs**: Be mindful of API usage during traffic generation (~$0.001 per request)

**Demo Data**: Use sample contracts, not real data

---

**Good luck with your submission! 🚀**
