from fuzzy_matcher import ApplicationMatcher, _resolve_current_status


def test_normalize_company_name():
    matcher = ApplicationMatcher()
    assert matcher._normalize_company_name("Acme Corp") == "acme"
    assert matcher._normalize_company_name("Generic GmbH") == "generic"
    assert matcher._normalize_company_name("StartUp SE") == "startup"
    assert matcher._normalize_company_name("Company LTD") == "company"


def test_fuzzy_matches_job_id_suffix():
    matcher = ApplicationMatcher()
    apps_cache = [
        {
            "id": "app-1",
            "company_name": "Schwarz",
            "job_title": "Junior Data Engineer (m/w/d)",
            "thread_id": "thread-1",
            "is_active": True,
        }
    ]

    match = matcher.find_existing_application(
        company_name="Schwarz",
        job_title="Junior Data Engineer (m/w/d) (3228)",
        thread_id="thread-2",
        apps_cache=apps_cache,
    )

    assert match is not None
    assert match["id"] == "app-1"


def test_fuzzy_matches_descriptive_kommissionierer_title():
    matcher = ApplicationMatcher()
    apps_cache = [
        {
            "id": "app-2",
            "company_name": "Servicebund",
            "job_title": "Kommissionierer (m/w/d)",
            "thread_id": "thread-3",
            "is_active": True,
        }
    ]

    match = matcher.find_existing_application(
        company_name="Servicebund",
        job_title="Kommissionierer (m/w/d) Bereich Trockenlager für die Früh- und Spätschicht",
        thread_id="thread-4",
        apps_cache=apps_cache,
    )

    assert match is not None
    assert match["id"] == "app-2"


def test_status_priority_prevents_regression():
    assert _resolve_current_status("Rejected", "Applied") == "Rejected"
