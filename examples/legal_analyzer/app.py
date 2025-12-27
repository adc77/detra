"""
Legal Document Analyzer - Example VertiGuard Application

This example demonstrates how to use VertiGuard for monitoring and evaluating
LLM-powered legal document processing with Datadog integration.

Usage:
    python app.py

Requires:
    - DD_API_KEY, DD_APP_KEY environment variables
    - GOOGLE_API_KEY for Gemini evaluation
"""

import asyncio
import json
import os
from typing import Any, Optional

import google.genai as genai
import structlog

import vertiguard

logger = structlog.get_logger()


# Sample legal document for testing
SAMPLE_CONTRACT = """
CONSULTING AGREEMENT

This Consulting Agreement ("Agreement") is entered into as of January 15, 2024,
by and between:

PARTY A: TechCorp Solutions Inc., a Delaware corporation with principal offices
at 123 Innovation Drive, San Francisco, CA 94105 ("Client")

PARTY B: Legal Advisory Partners LLC, a California limited liability company
with principal offices at 456 Law Street, Los Angeles, CA 90001 ("Consultant")

1. TERM
This Agreement shall commence on January 15, 2024 and continue until
December 31, 2024, unless earlier terminated pursuant to Section 8.

2. COMPENSATION
Client agrees to pay Consultant a monthly retainer of USD $15,000.00, payable
on the first business day of each month. Additional services beyond the scope
of this Agreement shall be billed at USD $500.00 per hour.

3. SCOPE OF SERVICES
Consultant shall provide legal advisory services including but not limited to:
- Contract review and negotiation
- Regulatory compliance guidance
- Intellectual property consultation

4. CONFIDENTIALITY
Both parties agree to maintain the confidentiality of all proprietary
information shared during the term of this Agreement.

5. GOVERNING LAW
This Agreement shall be governed by the laws of the State of California.

SIGNATURES:

_______________________
John Smith, CEO
TechCorp Solutions Inc.
Date: January 15, 2024

_______________________
Sarah Johnson, Managing Partner
Legal Advisory Partners LLC
Date: January 15, 2024
"""


class LegalDocumentAnalyzer:
    """
    LLM-powered legal document analyzer with VertiGuard observability.

    Demonstrates:
    - Using VertiGuard decorators for tracing
    - Entity extraction from legal documents
    - Document summarization
    - Question answering with citations
    """

    def __init__(self, config_path: str = "vertiguard.yaml"):
        """
        Initialize the analyzer with VertiGuard.

        Args:
            config_path: Path to vertiguard.yaml configuration file.
        """
        # Initialize VertiGuard
        self.vg = vertiguard.init(config_path)

        # Initialize Gemini for document processing
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        self.client = genai.Client(api_key=api_key)

        logger.info("LegalDocumentAnalyzer initialized")

    @vertiguard.trace("extract_entities")
    async def extract_entities(self, document: str) -> dict[str, Any]:
        """
        Extract legal entities from a document.

        Args:
            document: The legal document text.

        Returns:
            Dictionary with parties, dates, and amounts.
        """
        prompt = f"""Analyze this legal document and extract key entities.
Return ONLY valid JSON with exactly these keys:
- "parties": list of party names with their roles
- "dates": list of dates in ISO 8601 format (YYYY-MM-DD)
- "amounts": list of monetary amounts with currency codes

Document:
{document}

JSON Output:"""

        response = await self._generate_content(prompt)

        # Parse and validate JSON response
        try:
            # Clean response - remove markdown code blocks if present
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            result = json.loads(text)

            # Ensure required keys exist
            return {
                "parties": result.get("parties", []),
                "dates": result.get("dates", []),
                "amounts": result.get("amounts", []),
            }
        except json.JSONDecodeError as e:
            logger.error("Failed to parse entity extraction response", error=str(e))
            return {"parties": [], "dates": [], "amounts": [], "error": str(e)}

    @vertiguard.trace("summarize_document")
    async def summarize_document(
        self, document: str, max_words: int = 200
    ) -> dict[str, Any]:
        """
        Summarize a legal document.

        Args:
            document: The legal document text.
            max_words: Maximum words in summary.

        Returns:
            Dictionary with summary and key terms.
        """
        prompt = f"""Summarize this legal document in under {max_words} words.
Focus on:
1. The main purpose of the document
2. Key obligations of each party
3. Important terms and conditions

Maintain a neutral, objective tone. Do not add opinions or interpretations.
Return JSON with keys: "summary", "key_terms", "obligations"

Document:
{document}

JSON Output:"""

        response = await self._generate_content(prompt)

        try:
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            result = json.loads(text)
            return {
                "summary": result.get("summary", ""),
                "key_terms": result.get("key_terms", []),
                "obligations": result.get("obligations", {}),
            }
        except json.JSONDecodeError as e:
            logger.error("Failed to parse summarization response", error=str(e))
            return {"summary": "", "key_terms": [], "obligations": {}, "error": str(e)}

    @vertiguard.trace("answer_query")
    async def answer_query(
        self, document: str, query: str
    ) -> dict[str, Any]:
        """
        Answer a question about a legal document.

        Args:
            document: The legal document text.
            query: The user's question.

        Returns:
            Dictionary with answer and citations.
        """
        prompt = f"""Answer the following question based ONLY on the provided document.
You MUST:
1. Only use information from the document
2. Cite specific sections when making claims
3. Say "I cannot determine this from the document" if the answer is not in the document
4. Do NOT provide legal advice or opinions

Question: {query}

Document:
{document}

Return JSON with keys: "answer", "citations", "confidence" (high/medium/low)

JSON Output:"""

        response = await self._generate_content(prompt)

        try:
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            result = json.loads(text)
            return {
                "answer": result.get("answer", ""),
                "citations": result.get("citations", []),
                "confidence": result.get("confidence", "low"),
            }
        except json.JSONDecodeError as e:
            logger.error("Failed to parse query response", error=str(e))
            return {"answer": "", "citations": [], "confidence": "low", "error": str(e)}

    async def _generate_content(self, prompt: str) -> Any:
        """
        Generate content using Gemini with async wrapper.

        Args:
            prompt: The prompt to send to Gemini.

        Returns:
            Gemini response object with text attribute.
        """
        loop = asyncio.get_event_loop()
        
        def generate():
            response = self.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
            )
            # Extract text from response
            if hasattr(response, "text"):
                return type("Response", (), {"text": response.text})()
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content"):
                    if hasattr(candidate.content, "parts"):
                        parts = candidate.content.parts
                        if parts and hasattr(parts[0], "text"):
                            text = parts[0].text
                            return type("Response", (), {"text": text})()
            # Fallback
            return type("Response", (), {"text": str(response)})()
        
        return await loop.run_in_executor(None, generate)

    async def process_document(self, document: str) -> dict[str, Any]:
        """
        Run full document processing pipeline.

        Args:
            document: The legal document text.

        Returns:
            Combined results from all processing steps.
        """
        logger.info("Starting document processing pipeline")

        # Run extraction and summarization in parallel
        entities_task = self.extract_entities(document)
        summary_task = self.summarize_document(document)

        entities, summary = await asyncio.gather(entities_task, summary_task)

        logger.info(
            "Document processing complete",
            entities_count=len(entities.get("parties", [])),
            summary_length=len(summary.get("summary", "")),
        )

        return {
            "entities": entities,
            "summary": summary,
        }

    async def close(self) -> None:
        """Close resources and flush telemetry."""
        await self.vg.close()


async def run_demo():
    """Run a demonstration of the legal document analyzer."""
    print("=" * 60)
    print("Legal Document Analyzer - VertiGuard Demo")
    print("=" * 60)

    # Check for required environment variables
    required_vars = ["DD_API_KEY", "DD_APP_KEY", "GOOGLE_API_KEY"]
    missing = [v for v in required_vars if not os.environ.get(v)]

    if missing:
        print(f"\nMissing required environment variables: {', '.join(missing)}")
        print("Please set these variables and try again.")
        print("\nExample:")
        print("  export DD_API_KEY=your_datadog_api_key")
        print("  export DD_APP_KEY=your_datadog_app_key")
        print("  export GOOGLE_API_KEY=your_google_api_key")
        return

    # Get the directory of this script for config path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "vertiguard.yaml")

    analyzer = LegalDocumentAnalyzer(config_path)

    try:
        # Process the sample contract
        print("\n1. Processing sample contract...")
        results = await analyzer.process_document(SAMPLE_CONTRACT)

        print("\n--- Entity Extraction Results ---")
        print(f"Parties: {json.dumps(results['entities'].get('parties', []), indent=2)}")
        print(f"Dates: {results['entities'].get('dates', [])}")
        print(f"Amounts: {results['entities'].get('amounts', [])}")

        print("\n--- Document Summary ---")
        print(results["summary"].get("summary", "No summary generated"))

        # Answer a sample question
        print("\n2. Answering query about the document...")
        query = "What is the monthly retainer amount and when is it payable?"
        answer = await analyzer.answer_query(SAMPLE_CONTRACT, query)

        print(f"\nQuestion: {query}")
        print(f"Answer: {answer.get('answer', 'No answer')}")
        print(f"Confidence: {answer.get('confidence', 'unknown')}")
        print(f"Citations: {answer.get('citations', [])}")

        # Setup monitors and dashboard (optional)
        print("\n3. Setting up Datadog monitors and dashboard...")
        try:
            setup_results = await analyzer.vg.setup_all()
            print(f"Created {len(setup_results.get('monitors', {}).get('default_monitors', []))} default monitors")
            print(f"Created {len(setup_results.get('monitors', {}).get('custom_monitors', []))} custom monitors")
            if setup_results.get("dashboard"):
                print(f"Dashboard URL: {setup_results['dashboard'].get('url', 'N/A')}")
        except Exception as e:
            print(f"Monitor/dashboard setup skipped: {e}")

        print("\n" + "=" * 60)
        print("Demo complete! Check your Datadog dashboard for traces and metrics.")
        print("=" * 60)

    finally:
        await analyzer.close()


async def run_interactive():
    """Run interactive mode for testing custom documents and queries."""
    print("Legal Document Analyzer - Interactive Mode")
    print("Commands: 'extract', 'summarize', 'query', 'quit'")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "vertiguard.yaml")

    analyzer = LegalDocumentAnalyzer(config_path)
    current_document: Optional[str] = None

    try:
        while True:
            cmd = input("\nCommand: ").strip().lower()

            if cmd == "quit":
                break
            elif cmd == "load":
                print("Enter document text (end with empty line):")
                lines = []
                while True:
                    line = input()
                    if not line:
                        break
                    lines.append(line)
                current_document = "\n".join(lines)
                print(f"Loaded document ({len(current_document)} characters)")
            elif cmd == "sample":
                current_document = SAMPLE_CONTRACT
                print("Loaded sample contract")
            elif cmd == "extract":
                if not current_document:
                    print("No document loaded. Use 'load' or 'sample' first.")
                    continue
                result = await analyzer.extract_entities(current_document)
                print(json.dumps(result, indent=2))
            elif cmd == "summarize":
                if not current_document:
                    print("No document loaded. Use 'load' or 'sample' first.")
                    continue
                result = await analyzer.summarize_document(current_document)
                print(json.dumps(result, indent=2))
            elif cmd == "query":
                if not current_document:
                    print("No document loaded. Use 'load' or 'sample' first.")
                    continue
                question = input("Question: ")
                result = await analyzer.answer_query(current_document, question)
                print(json.dumps(result, indent=2))
            else:
                print("Unknown command. Use: load, sample, extract, summarize, query, quit")
    finally:
        await analyzer.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(run_interactive())
    else:
        asyncio.run(run_demo())
