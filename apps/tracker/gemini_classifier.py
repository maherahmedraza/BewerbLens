# ╔══════════════════════════════════════════════════════════════╗
# ║  Gemini Classifier — AI email classification                ║
# ║  Implementation of EmailClassifier using Google Gemini.      ║
# ║                                                             ║
# ║  v3.0: Refactored into a class, uses adaptive token-based   ║
# ║  batching and optimized prompts.                             ║
# ╚══════════════════════════════════════════════════════════════╝

import json
import re
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
CLASSIFICATION_PROMPT = """You are a job application email classifier for a German job seeker.
Classify each email into exactly one of 4 types. Return ONLY valid JSON that matches the provided response schema.

TYPES:
1. "application_confirmation" - Company confirmed receiving YOUR job application
2. "rejection" - Application was declined
3. "positive_response" - Interview invite, assessment, or offer
4. "not_job_related" - Everything else (job alerts, newsletters, etc)

EXTRACTION:
- company_name: The HIRING company, NOT the platform (e.g., extract from body if sender is SmartRecruiters)
- job_title: Exact role title or "Not Specified"
- platform: SmartRecruiters, Personio, Workday, Lever, Greenhouse, Softgarden, JOIN, StepStone, Indeed, Xing, LinkedIn, Direct
- location: City/Remote or empty string
- job_listing_url: If found in body
- confidence: 0.0 to 1.0

EMAILS:
{emails_text}

JSON response object:
{{"results":[{{"email_index":1,"classification":"...","company_name":"...","job_title":"...","platform":"...","location":"...","job_listing_url":"","salary_range":"","confidence":0.9,"reasoning":"..."}}]}}"""


class GeminiClassifier(EmailClassifier):
    """
    Implementación de EmailClassifier para Google Gemini.
    Optimiza el consumo de tokens y utiliza batching adaptativo.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model
        self.max_tokens = settings.classifier_max_batch_tokens

    @property
    def provider_name(self) -> str:
        return "gemini"

    def classify(self, emails: list[EmailMetadata]) -> list[EmailClassification]:
        """
        Clasifica emails usando batching adaptativo por conteo de tokens (estimado).
        """
        if not emails:
            return []

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
                raw_response = self._call_api(prompt)
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
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
            "response_json_schema": GeminiBatchResponse.model_json_schema(),
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        reraise=True,
    )
    def _call_api(self, prompt: str) -> str:
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
        return text or response.text or ""

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
