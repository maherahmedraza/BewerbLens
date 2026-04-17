import pytest
from fuzzy_matcher import ApplicationMatcher
from loguru import logger

def test_normalize_company_name():
    matcher = ApplicationMatcher()
    assert matcher._normalize_company_name("Acme Corp") == "acme"
    assert matcher._normalize_company_name("Generic GmbH") == "generic"
    assert matcher._normalize_company_name("StartUp SE") == "startup"
    assert matcher._normalize_company_name("Company LTD") == "company"
