import pytest
from supabase_service import _strip_stopwords
from loguru import logger

def test_strip_stopwords():
    assert _strip_stopwords("Acme Corp") == "acme"
    assert _strip_stopwords("Generic GmbH") == "generic"
    assert _strip_stopwords("StartUp SE") == "startup"
    assert _strip_stopwords("Company LTD") == "company"
