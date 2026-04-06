# ╔══════════════════════════════════════════════════════════════╗
# ║  Gemini Classifier — AI email classification                ║
# ║  Replaces the "Build Gemini Batches",                       ║
# ║  "Gemini API Call" and "Expand Results" nodes.              ║
# ║                                                             ║
# ║  v2.0: Extracts location, job_listing_url, salary_range.    ║
# ╚══════════════════════════════════════════════════════════════╝

import json
import re
import time

from google import genai
from google.genai import types
from loguru import logger
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from models import (
    Classification,
    EmailClassification,
    EmailMetadata,
    GeminiBatchResponse,
)

# System prompt — enhanced with new extraction fields
CLASSIFICATION_PROMPT = """You are a job application email classifier for a German job seeker.
Classify each email into exactly one of 4 types. Return ONLY valid JSON.

TYPES:
1. "application_confirmation" - Company confirmed receiving YOUR job application
   → Eingangsbestätigung, Bewerbung erhalten, Vielen Dank für Ihre/deine Bewerbung,
     we received your application, application confirmed, Your Application - [Title],
     Deine Bewerbung bei [Company], wir haben Ihre Unterlagen erhalten

2. "rejection" - Application was declined
   → leider absagen, leider müssen wir, andere Kandidaten, unfortunately,
     cannot offer, unable to proceed, nicht berücksichtigen, we regret,
     have decided to move forward with other candidates

3. "positive_response" - Interview invite, assessment, or offer
   → einladen, Vorstellungsgespräch, Kennenlerngespräch, assessment,
     we would like to invite, next steps, please schedule, können wir einen Termin

4. "not_job_related" - Anything else
   → job alerts, newsletters, OTP codes, account confirmations, marketing

EXTRACTION:
- company_name: The HIRING company, NOT the ATS/platform
  * "Bosch Group <notifications@smartrecruiters.com>" → "Robert Bosch GmbH"
  * "HR <e113-jobs@m.personio.de>" → extract from body or use "E113"
  * "anna@dekra.com" → "DEKRA"
  * NEVER use: SmartRecruiters, Personio, Workday, Lever, Greenhouse, Workwise, Onlyfy

- job_title: Exact role title.
  * Look for "Position:", "Job Title:", "Role:", "(m/f/d)", or similar markers.
  * If the subject line contains a role (e.g., "Sortation Associate"), use it.
  * Use "Not Specified" ONLY if absolutely no role is mentioned.

- platform:
  smartrecruiters.com/onlyfy.jobs→SmartRecruiters, m.personio.de→Personio,
  workday.com→Workday, lever.co→Lever, greenhouse.io→Greenhouse,
  successfactors.eu/com→SAP SuccessFactors, softgarden.io→Softgarden,
  recruitee.com→Recruitee, workwise.io→Workwise,
  jobs.amazon.com→Amazon Jobs, join.com→JOIN, stepstone.de→StepStone,
  indeed.com→Indeed, xing.com→Xing, linkedin.com→LinkedIn,
  company own domain→Direct, unknown→Direct

- location: City or region of the job. "Remote" if remote. Empty string if not mentioned.

- confidence: 0.9+=very clear, 0.7-0.89=likely, 0.55-0.69=uncertain, <0.55=not_job_related
  * A clear "thank you for applying" or "application received" MUST be at least 0.90 confidence.
  * A clear "leider absagen" or "unfortunately" rejection MUST be at least 0.90 confidence.

EMAILS:
{emails_text}

JSON response only (return an array of objects):
[{{"email_index":1,"classification":"application_confirmation","company_name":"Company","job_title":"Title","platform":"Platform","location":"City","job_listing_url":"","salary_range":"","confidence":0.95,"reasoning":"Brief reason"}}]"""


def _configure_gemini() -> genai.Client:
    """Configures and returns the Gemini client with the environment key."""
    return genai.Client(api_key=settings.gemini_api_key)


def _format_email_for_prompt(email: EmailMetadata, index: int) -> str:
    """Formats an email as text to include in the prompt."""
    return (
        f"=== EMAIL {index + 1} ===\n"
        f"Subject: {email.subject}\n"
        f"From: {email.sender}\n"
        f"Date: {email.date.isoformat()}\n"
        f"Body:\n{email.body or '(empty)'}"
    )


def _parse_gemini_response(raw_text: str, batch_size: int) -> list[EmailClassification]:
    """
    Parses Gemini's response with multiple fallback strategies.
    Handles both {"results": [...]} and bare [...] formats.
    """
    # Clean code delimiters
    cleaned = re.sub(r"```json\s*", "", raw_text)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()

    # Find JSON boundaries — could be object or array
    first_brace = cleaned.find("{")
    first_bracket = cleaned.find("[")
    last_brace = cleaned.rfind("}")
    last_bracket = cleaned.rfind("]")

    first_char_idx = -1
    last_char_idx = -1

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        first_char_idx = first_brace
        last_char_idx = last_brace
    elif first_bracket != -1:
        first_char_idx = first_bracket
        last_char_idx = last_bracket

    if first_char_idx == -1 or last_char_idx == -1:
        logger.bind(response_preview=raw_text[:200]).error("No JSON found in Gemini response")
        return []

    json_str = cleaned[first_char_idx : last_char_idx + 1]

    # Try to parse directly
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        # Try to clean trailing commas (common LLM error)
        try:
            fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
            parsed = json.loads(fixed)
        except json.JSONDecodeError as error:
            logger.bind(error=str(error), preview=json_str[:500]).error("JSON parse failed after cleanup")
            return []

    # Handle bare array response: [{"email_index": 1, ...}, ...]
    if isinstance(parsed, list):
        results = []
        for i, item in enumerate(parsed):
            try:
                if isinstance(item, dict) and "email_index" not in item:
                    item["email_index"] = i + 1
                result = EmailClassification.model_validate(item)
                results.append(result)
            except (ValidationError, TypeError):
                continue
        return results

    # Handle object response: {"results": [...]}
    try:
        batch_response = GeminiBatchResponse.model_validate(parsed)
        return batch_response.results
    except ValidationError:
        pass

    # Fallback: try to extract results manually
    results = []
    raw_results = parsed.get("results", parsed.get("data", []))
    if isinstance(raw_results, list):
        for i, raw in enumerate(raw_results):
            try:
                if isinstance(raw, dict) and "email_index" not in raw:
                    raw["email_index"] = i + 1
                result = EmailClassification.model_validate(raw)
                results.append(result)
            except (ValidationError, TypeError):
                continue
    return results


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True,
)
def _call_gemini(client: genai.Client, prompt: str) -> str:
    """
    Calls the Gemini API with automatic retries.
    tenacity handles rate limiting and transient errors.
    """
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.05,
            max_output_tokens=4096,
            response_mime_type="application/json",
        ),
    )

    # Extract text ignoring thinking parts (for Gemini 3+ models)
    text = ""
    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "thought") and part.thought:
                continue
            if part.text:
                text = part.text
                break

    if not text:
        text = response.text or ""

    return text


def classify_emails(emails: list[EmailMetadata]) -> list[EmailClassification]:
    """
    Classifies a list of emails using Gemini in batches.
    Returns a list of classifications, one per email.

    v2.0: Extracts location, job_listing_url, salary_range fields.
    """
    client = _configure_gemini()
    batch_size = settings.batch_size
    all_results: list[EmailClassification] = []

    # Split into batches
    batches = [emails[i : i + batch_size] for i in range(0, len(emails), batch_size)]
    logger.bind(
        total_emails=len(emails),
        batches=len(batches),
        batch_size=batch_size,
        model=settings.gemini_model,
    ).info("Starting Gemini classification")

    for batch_idx, batch in enumerate(batches):
        # Rate limiting between batches
        if batch_idx > 0:
            logger.debug(f"Rate limit delay: 2s before batch {batch_idx + 1}/{len(batches)}")
            time.sleep(2)

        # Build the prompt with the batch emails
        emails_text = "\n\n---\n\n".join(
            _format_email_for_prompt(email, i) for i, email in enumerate(batch)
        )
        prompt = CLASSIFICATION_PROMPT.format(emails_text=emails_text)

        try:
            raw_response = _call_gemini(client, prompt)
            results = _parse_gemini_response(raw_response, len(batch))

            logger.bind(
                batch=batch_idx + 1,
                total_batches=len(batches),
                results=len(results),
                expected=len(batch),
            ).info("Batch classified")

            # Map results to original emails in the batch
            result_map: dict[int, EmailClassification] = {}
            for r in results:
                idx = r.email_index - 1  # Gemini uses 1-based index
                if 0 <= idx < len(batch):
                    result_map[idx] = r

            # Sequential fallback if indices don't match
            if not result_map and results:
                for i, r in enumerate(results):
                    if i < len(batch):
                        result_map[i] = r

            # Ensure every email has a result
            for i in range(len(batch)):
                if i in result_map:
                    all_results.append(result_map[i])
                else:
                    # Email without classification -> mark as not_job_related
                    logger.bind(
                        batch=batch_idx + 1,
                        email_index=i + 1,
                        subject=batch[i].subject[:50],
                    ).warning("No Gemini result for email")
                    all_results.append(
                        EmailClassification(
                            email_index=i + 1,
                            classification=Classification.NOT_JOB_RELATED,
                            company_name="Unknown",
                            confidence=0.0,
                            reasoning="No classification returned by Gemini",
                        )
                    )

        except Exception as error:
            logger.bind(
                batch=batch_idx + 1,
                error=str(error),
            ).error("Gemini batch failed after retries")
            # Mark entire batch as error
            for i in range(len(batch)):
                all_results.append(
                    EmailClassification(
                        email_index=i + 1,
                        classification=Classification.NOT_JOB_RELATED,
                        company_name="Error",
                        confidence=0.0,
                        reasoning=f"API error: {str(error)[:200]}",
                    )
                )

    return all_results
