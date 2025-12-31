#!/usr/bin/env python3
"""
Legal AI Agent Service - Detra Observability Demo

A FastAPI service for legal document analysis demonstrating detra observability:
- Agent workflow tracking with tool calls
- LLM adherence monitoring
- Error tracking
- Security scanning (PII, prompt injection)
- Datadog integration

Run: uvicorn examples.legal_analyzer.service:app --reload --port 8000
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import google.genai as genai
import structlog

import detra
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

app = FastAPI(
    title="Legal AI Agent Service",
    description="Legal document analysis with detra observability",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_vg = None
_client = None
_start_time = None


# =============================================================================
# MODELS
# =============================================================================

class AnalyzeRequest(BaseModel):
    document: str = Field(..., min_length=10)
    query: Optional[str] = None
    search_context: bool = False


class AnalyzeResponse(BaseModel):
    workflow_id: str
    entities: dict
    summary: dict
    answer: Optional[dict] = None
    search_results: Optional[list] = None
    latency_ms: float


class SimpleRequest(BaseModel):
    document: str = Field(..., min_length=10)


# =============================================================================
# WEB SEARCH TOOL
# =============================================================================

class WebSearchTool:
    """Web search for legal context."""

    async def search(self, query: str, num_results: int = 3) -> list[dict]:
        """Search web for legal information."""
        api_key = os.getenv("SERPER_API_KEY")

        if not api_key:
            return self._mock_results(query)

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": api_key},
                    json={"q": f"legal {query}", "num": num_results},
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    {"title": r.get("title"), "snippet": r.get("snippet"), "link": r.get("link")}
                    for r in data.get("organic", [])[:num_results]
                ]
            except Exception:
                return self._mock_results(query)

    def _mock_results(self, query: str) -> list[dict]:
        return [
            {"title": f"Legal Analysis: {query[:30]}", "snippet": "According to case law...", "link": "https://example.com/1"},
            {"title": "Contract Law Reference", "snippet": "Standard provisions include...", "link": "https://example.com/2"},
        ]


# =============================================================================
# LEGAL AI AGENT
# =============================================================================

class LegalAgent:
    """Legal AI Agent with detra observability."""

    def __init__(self, vg, client, model: str = "gemini-2.5-flash"):
        self.vg = vg
        self.client = client
        self.model = model
        self.search = WebSearchTool()

    async def analyze(self, document: str, query: Optional[str] = None, search_context: bool = False) -> dict:
        """Full document analysis with agent workflow."""
        start = time.time()

        workflow_id = self.vg.agent_monitor.start_workflow(
            "legal_agent",
            metadata={"doc_len": len(document), "has_query": bool(query)},
        )

        result = {"workflow_id": workflow_id, "entities": {}, "summary": {}, "answer": None, "search_results": None}

        try:
            self.vg.agent_monitor.track_thought(workflow_id, "Starting document analysis")
            self.vg.agent_monitor.track_decision(workflow_id, "analyze_full", "Standard legal analysis workflow", 0.95)

            # Web search if enabled
            if search_context and query:
                self.vg.agent_monitor.track_action(workflow_id, "web_search", {"query": query})
                t = time.time()
                search_results = await self.search.search(query)
                self.vg.agent_monitor.track_tool_call(workflow_id, "web_search", {"query": query},
                    {"count": len(search_results)}, (time.time() - t) * 1000)
                self.vg.agent_monitor.track_observation(workflow_id, f"Found {len(search_results)} results")
                result["search_results"] = search_results

            # Extract entities
            self.vg.agent_monitor.track_action(workflow_id, "extract_entities", {})
            t = time.time()
            entities = await self._extract_entities(document)
            self.vg.agent_monitor.track_tool_call(workflow_id, "llm_extract", {}, entities, (time.time() - t) * 1000)
            self.vg.agent_monitor.track_observation(workflow_id, f"Extracted {len(entities.get('parties', []))} parties")
            result["entities"] = entities

            # Summarize
            self.vg.agent_monitor.track_action(workflow_id, "summarize", {})
            t = time.time()
            summary = await self._summarize(document)
            self.vg.agent_monitor.track_tool_call(workflow_id, "llm_summarize", {}, summary, (time.time() - t) * 1000)
            result["summary"] = summary

            # Answer query
            if query:
                self.vg.agent_monitor.track_action(workflow_id, "answer_query", {"query": query})
                ctx = "\n".join([f"- {r['snippet']}" for r in (result.get("search_results") or [])])
                t = time.time()
                answer = await self._answer(document, query, ctx)
                self.vg.agent_monitor.track_tool_call(workflow_id, "llm_answer", {"query": query}, answer, (time.time() - t) * 1000)
                result["answer"] = answer

            self.vg.agent_monitor.complete_workflow(workflow_id, result)
            result["latency_ms"] = (time.time() - start) * 1000
            return result

        except Exception as e:
            self.vg.agent_monitor.fail_workflow(workflow_id, str(e))
            self.vg.error_tracker.capture_exception(e, context={"workflow_id": workflow_id}, level="error")
            raise

    @detra.trace("extract_entities")
    async def _extract_entities(self, document: str) -> dict:
        prompt = f"""Extract entities from this legal document. Return ONLY valid JSON.

REQUIREMENTS:
- Only extract entities explicitly in the document
- Do NOT fabricate information
- Dates in YYYY-MM-DD format
- Include currency with amounts

Document:
{document}

JSON:
{{"parties": [], "dates": [], "amounts": [], "obligations": []}}"""

        return self._parse_json(await self._llm(prompt))

    @detra.trace("summarize_document")
    async def _summarize(self, document: str) -> dict:
        prompt = f"""Summarize this legal document in under 200 words.

REQUIREMENTS:
- Neutral, objective tone
- Focus on key terms and obligations
- Do NOT add opinions

Document:
{document}

JSON:
{{"summary": "", "key_terms": [], "obligations": []}}"""

        return self._parse_json(await self._llm(prompt))

    @detra.trace("answer_query")
    async def _answer(self, document: str, query: str, context: str = "") -> dict:
        prompt = f"""Answer based ONLY on the document.

Question: {query}

Document:
{document}

Additional Context:
{context}

REQUIREMENTS:
- Only use document information
- Cite sections
- Say "Not found" if not in document
- Do NOT give legal advice

JSON:
{{"answer": "", "citations": [], "confidence": 0.0}}"""

        return self._parse_json(await self._llm(prompt))

    async def _llm(self, prompt: str) -> str:
        loop = asyncio.get_event_loop()
        def call():
            r = self.client.models.generate_content(model=self.model, contents=prompt)
            return r.text if hasattr(r, "text") else str(r)
        return await loop.run_in_executor(None, call)

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        for prefix in ["```json", "```"]:
            if text.startswith(prefix):
                text = text[len(prefix):]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse JSON from LLM response",
                error=str(e),
                position=e.pos,
                raw_preview=text[:300],
            )
            return {
                "error": "Invalid JSON",
                "error_type": "JSONDecodeError",
                "error_message": str(e),
                "raw": text[:300],
            }


# =============================================================================
# STARTUP
# =============================================================================

@app.on_event("startup")
async def startup():
    global _vg, _client, _start_time
    _start_time = time.time()

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY required")

    config_path = Path(__file__).parent / "detra.yaml"
    _vg = detra.init(str(config_path))
    _client = genai.Client(api_key=api_key)

    if os.getenv("DD_API_KEY"):
        try:
            await _vg.setup_all()
        except Exception as e:
            logger.warning("Datadog setup failed", error=str(e))

    logger.info("Legal AI Service started")


@app.on_event("shutdown")
async def shutdown():
    if _vg:
        await _vg.close()


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
async def health():
    return {"status": "healthy", "uptime": time.time() - _start_time if _start_time else 0}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Full document analysis with agent workflow tracking."""
    if not _vg or not _client:
        raise HTTPException(503, "Not initialized")

    _vg.error_tracker.add_breadcrumb("analyze request", category="api")
    agent = LegalAgent(_vg, _client)
    return await agent.analyze(request.document, request.query, request.search_context)


@app.post("/extract")
async def extract(request: SimpleRequest):
    """Extract entities from document."""
    if not _vg or not _client:
        raise HTTPException(503, "Not initialized")
    agent = LegalAgent(_vg, _client)
    return await agent._extract_entities(request.document)


@app.post("/summarize")
async def summarize(request: SimpleRequest):
    """Summarize document."""
    if not _vg or not _client:
        raise HTTPException(503, "Not initialized")
    agent = LegalAgent(_vg, _client)
    return await agent._summarize(request.document)


@app.get("/errors")
async def errors():
    """Get captured errors."""
    if not _vg:
        raise HTTPException(503, "Not initialized")
    return {
        "total": _vg.error_tracker.total_errors,
        "unique": _vg.error_tracker.unique_errors,
        "errors": _vg.error_tracker.get_all_errors(),
    }


@app.get("/workflows")
async def workflows():
    """Get active workflows."""
    if not _vg:
        raise HTTPException(503, "Not initialized")
    active = _vg.agent_monitor.get_active_workflows()
    return {"active": len(active), "workflows": [{"id": w.workflow_id, "steps": len(w.steps)} for w in active]}


@app.post("/trigger-error")
async def trigger_error(error_type: str = "ValueError"):
    """Trigger test error for demo."""
    if not _vg:
        raise HTTPException(503, "Not initialized")

    _vg.error_tracker.add_breadcrumb("Test error triggered", category="test")

    errors = {"ValueError": ValueError, "KeyError": KeyError, "TypeError": TypeError}
    exc_class = errors.get(error_type, RuntimeError)

    try:
        raise exc_class(f"Test {error_type}")
    except Exception as e:
        error_id = _vg.error_tracker.capture_exception(e, context={"test": True}, level="error")
        return {"error_id": error_id, "type": type(e).__name__, "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
