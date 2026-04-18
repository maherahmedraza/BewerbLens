import os
os.environ["GEMINI_API_KEY"] = "dummy_for_tests"
from gemini_classifier import GeminiClassifier


def test_parse_gemini_response_valid():
    response = """JSON response only:
[{"email_index": 1, "classification": "application_confirmation", "company_name": "Google", "confidence": 0.9}]"""
    
    classifier = GeminiClassifier()
    parsed = classifier._parse_response(response)
    assert len(parsed) == 1
    assert parsed[0].company_name == "Google"

def test_parse_gemini_response_trailing_comma():
    # Common error from LLMs: trailing comma
    # Note: json.loads might fail on strict trailing comma, but our logic handles list vs dict
    response = """
[
    {"email_index": 1, "classification": "rejection", "company_name": "Apple", "confidence": 0.99}
]
"""
    
    classifier = GeminiClassifier()
    parsed = classifier._parse_response(response)
    assert len(parsed) == 1
    assert parsed[0].company_name == "Apple"


def test_parse_gemini_response_structured_results_object():
    response = """
    {
        "results": [
            {
                "email_index": 1,
                "classification": "positive_response",
                "company_name": "Stripe",
                "job_title": "Backend Engineer",
                "platform": "Greenhouse",
                "location": "Berlin",
                "job_listing_url": "https://jobs.example/123",
                "salary_range": "",
                "confidence": 0.97,
                "reasoning": "Interview invitation detected."
            }
        ]
    }
    """

    classifier = GeminiClassifier()
    parsed = classifier._parse_response(response)

    assert len(parsed) == 1
    assert parsed[0].classification == "positive_response"
    assert parsed[0].company_name == "Stripe"
    assert parsed[0].job_title == "Backend Engineer"


def test_generation_config_includes_structured_output_schema():
    classifier = GeminiClassifier()

    config = classifier._generation_config()

    assert config["response_mime_type"] == "application/json"
    assert "response_json_schema" in config
    assert config["response_json_schema"]["type"] == "object"
    assert "results" in config["response_json_schema"]["properties"]
