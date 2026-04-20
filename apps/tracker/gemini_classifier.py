from __future__ import annotations

# ╔══════════════════════════════════════════════════════════════╗
# ║  Gemini Classifier — AI email classification                ║
# ║  Implementation of EmailClassifier using Google Gemini.      ║
# ║                                                             ║
# ║  v3.0: Refactored into a class, uses adaptive token-based   ║
# ║  batching and optimized prompts.                             ║
# ╚══════════════════════════════════════════════════════════════╝

import re
import json
import time
from typing import Any

from google import genai
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
from classifier_base import EmailClassifier

# System prompt — optimized for performance and structure
CLASSIFICATION_PROMPT = """You are an expert job application email classifier for a German-based job seeker.
Classify each email into exactly one of 4 types. The emails may be in English or German.
Return ONLY valid JSON that matches the provided response schema.

TYPES:
1. "application_confirmation" - Company confirmed receiving YOUR job application (e.g., "Eingangsbestätigung", "vielen Dank für Ihre Bewerbung")
2. "rejection" - Application was declined (e.g., "Absage", "Leider müssen wir Ihnen heute mitteilen", "nicht weiter berücksichtigen", "nicht weiter verfolgen")
3. "positive_response" - Interview invite, assessment, or offer (e.g., "Einladung zum Vorstellungsgespräch", "nächste Schritte", "Interview")
4. "not_job_related" - Everything else (job alerts, marketing, internal company news)

EXTRACTION RULES:
- company_name: The actual HIRING company (e.g., "Körber", "Schwarz Digits").
- job_title: Exact role title.
- platform: SmartRecruiters, Personio, Workday, Greenhouse, JOIN, Direct, etc.
- location: Best single-line job location summary, if present.
- job_location: Full structured location text from the email, if present.
- job_city: City only, if present.
- job_country: Country only, if present.
- work_mode: One of "Remote", "Hybrid", "On-site", or "Unknown".
- confidence: 0.0 to 1.0

EMAILS TO CLASSIFY:
{emails_text}

JSON response format:
{{"results":[{{"email_index":1,"classification":"...","company_name":"...","job_title":"...","platform":"...","location":"...","job_location":"","job_city":"","job_country":"","work_mode":"Unknown","job_listing_url":"","salary_range":"","confidence":0.9,"reasoning":"..."}}]}}"""


class GeminiClassifier(EmailClassifier):
    """
    Implementación de EmailClassifier para Google Gemini.
    Optimiza el consumo de tokens y utiliza batching adaptativo.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model
        self.max_tokens = settings.classifier_max_batch_tokens
        self.last_usage = self._empty_usage()

    @property
    def provider_name(self) -> str:
        return "gemini"

    def classify(self, emails: list[EmailMetadata]) -> list[EmailClassification]:
        """
        Clasifica emails usando batching adaptativo por conteo de tokens (estimado).
        """
        if not emails:
            return []

        self.last_usage = self._empty_usage()
        all_results: list[EmailClassification] = []
        batches = self._create_adaptive_batches(emails)

        logger.bind(
            total_emails=len(emails),
            batches=len(batches),
            model=self.model,
        ).info(f"Starting {self.provider_name} adaptive classification")

        for batch_idx, batch in enumerate(batches):
            if batch_idx > 0:
                time.sleep(2)  # Rate limiting básico

            emails_text = "\n\n---\n\n".join(
                self._format_email(email, i) for i, email in enumerate(batch)
            )
            prompt = CLASSIFICATION_PROMPT.format(emails_text=emails_text)

            try:
                raw_response, usage = self._call_api(prompt)
                self._accumulate_usage(usage)
                results = self._parse_response(raw_response)

                # Mapeo de resultados
                result_map = {r.email_index - 1: r for r in results if 0 <= r.email_index - 1 < len(batch)}
                
                # Rellenar huecos si falló alguna clasificación individual
                for i in range(len(batch)):
                    if i in result_map:
                        all_results.append(result_map[i])
                    else:
                        all_results.append(self._get_error_classification(i + 1, "Missing result"))

            except Exception as e:
                err_msg = str(e)
                if "API key expired" in err_msg or "API_KEY_INVALID" in err_msg:
                    logger.critical(f"CRITICAL: Gemini API Key is invalid or expired. Pipeline aborted.")
                    raise RuntimeError("Gemini API Key expired. Please update GEMINI_API_KEY in .env.") from e
                
                logger.error(f"Batch {batch_idx + 1} failed: {e}")
                for i in range(len(batch)):
                    all_results.append(self._get_error_classification(i + 1, err_msg))

        return all_results

    def _create_adaptive_batches(self, emails: list[EmailMetadata]) -> list[list[EmailMetadata]]:
        """
        Crea lotes basados en el tamaño de caracteres (estimación de tokens).
        """
        batches = []
        current_batch = []
        current_size = 0
        
        # Factor de conversión conservador: 4 caracteres ~ 1 token
        # max_tokens * 4 = max_chars
        max_chars = self.max_tokens * 4

        for email in emails:
            # Cuerpo truncado según configuración
            truncated_body = email.body[:settings.prompt_body_max_chars]
            email_size = len(email.subject) + len(email.sender) + len(truncated_body)

            if current_batch and (current_size + email_size > max_chars):
                batches.append(current_batch)
                current_batch = [email]
                current_size = email_size
            else:
                current_batch.append(email)
                current_size += email_size
        
        if current_batch:
            batches.append(current_batch)
            
        return batches

    def _format_email(self, email: EmailMetadata, index: int) -> str:
        """Formatea email truncando el cuerpo para optimizar tokens."""
        body = email.body[:settings.prompt_body_max_chars]
        return (
            f"=== EMAIL {index + 1} ===\n"
            f"Subject: {email.subject}\n"
            f"From: {email.sender}\n"
            f"Body: {body}"
        )

    def _generation_config(self) -> dict[str, Any]:
        return {
            "temperature": 0.05,
            "max_output_tokens": 4096,
            "response_mime_type": "application/json",
            "response_json_schema": GeminiBatchResponse.model_json_schema(),
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        reraise=True,
    )
    def _call_api(self, prompt: str) -> tuple[str, dict[str, float]]:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=self._generation_config(),
        )
        # Extraer texto ignorando "thinking" parts
        text = ""
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "thought") and part.thought:
                    continue
                if part.text:
                    text = part.text
                    break
        return text or response.text or "", self._extract_usage(response)

    def _empty_usage(self) -> dict[str, float]:
        return {
            "ai_requests": 0,
            "ai_input_tokens_est": 0,
            "ai_output_tokens_est": 0,
            "ai_estimated_cost_usd": 0.0,
        }

    def _accumulate_usage(self, usage: dict[str, float]) -> None:
        self.last_usage["ai_requests"] += int(usage.get("ai_requests", 0))
        self.last_usage["ai_input_tokens_est"] += int(usage.get("ai_input_tokens_est", 0))
        self.last_usage["ai_output_tokens_est"] += int(usage.get("ai_output_tokens_est", 0))
        self.last_usage["ai_estimated_cost_usd"] = round(
            float(self.last_usage["ai_estimated_cost_usd"])
            + float(usage.get("ai_estimated_cost_usd", 0.0)),
            6,
        )

    def _extract_usage(self, response: Any) -> dict[str, float]:
        usage_metadata = getattr(response, "usage_metadata", None)
        prompt_tokens = self._usage_value(usage_metadata, "prompt_token_count", "promptTokenCount")
        output_tokens = self._usage_value(
            usage_metadata,
            "candidates_token_count",
            "candidatesTokenCount",
            "output_token_count",
            "outputTokenCount",
        )
        estimated_cost = (
            (prompt_tokens / 1_000_000) * settings.gemini_input_cost_per_million
            + (output_tokens / 1_000_000) * settings.gemini_output_cost_per_million
        )
        return {
            "ai_requests": 1,
            "ai_input_tokens_est": prompt_tokens,
            "ai_output_tokens_est": output_tokens,
            "ai_estimated_cost_usd": round(estimated_cost, 6),
        }

    def _usage_value(self, usage_metadata: Any, *names: str) -> int:
        if usage_metadata is None:
            return 0

        for name in names:
            value = getattr(usage_metadata, name, None)
            if value is None and isinstance(usage_metadata, dict):
                value = usage_metadata.get(name)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return 0
        return 0

    def _parse_response(self, raw_text: str) -> list[EmailClassification]:
        """Lógica robusta de parseo JSON."""
        # Limpieza básica
        cleaned = re.sub(r"```json\s*", "", raw_text)
        cleaned = re.sub(r"```\s*", "", cleaned).strip()
        
        # Robustness: find first '[' or '{' to ignore prefix text
        match = re.search(r"(\[|\{)", cleaned)
        if match:
            cleaned = cleaned[match.start():]
            # Also find last ']' or '}'
            last_match = re.search(r"(\]|\})(?!.*(\]|\}))", cleaned, re.DOTALL)
            if last_match:
                cleaned = cleaned[:last_match.end()]

        try:
            batch_response = GeminiBatchResponse.model_validate_json(cleaned)
            return batch_response.results
        except ValidationError:
            pass

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                try:
                    return GeminiBatchResponse.model_validate(parsed).results
                except ValidationError:
                    items = parsed.get("results")
            elif isinstance(parsed, list):
                items = parsed
            else:
                return []

            if not isinstance(items, list):
                return []

            results = []
            for item in items:
                try:
                    results.append(EmailClassification.model_validate(item))
                except ValidationError:
                    continue
            return results
        except Exception as e:
            logger.error(f"Fallo al parsear JSON de Gemini: {e}")
            return []

    def _get_error_classification(self, index: int, msg: str) -> EmailClassification:
        return EmailClassification(
            email_index=index,
            classification=Classification.NOT_JOB_RELATED,
            company_name="Error",
            confidence=0.0,
            reasoning=f"Error en clasificación: {msg[:100]}"
        )
