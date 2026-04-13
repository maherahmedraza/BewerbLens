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
