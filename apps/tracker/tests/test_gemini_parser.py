import pytest
from gemini_classifier import _parse_gemini_response

def test_parse_gemini_response_valid():
    response = """JSON response only:
[{"email_index": 1, "classification": "application_confirmation", "company_name": "Google", "confidence": 0.9}]"""
    
    parsed = _parse_gemini_response(response, 1)
    assert len(parsed) == 1
    assert parsed[0].company_name == "Google"

def test_parse_gemini_response_trailing_comma():
    # Common error from LLMs: trailing comma
    response = """
[
    {"email_index": 1, "classification": "rejection", "company_name": "Apple", "confidence": 0.99},
]
"""
    
    parsed = _parse_gemini_response(response, 1)
    assert len(parsed) == 1
    assert parsed[0].classification == "rejection"
