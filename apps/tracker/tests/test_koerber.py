from fuzzy_matcher import ApplicationMatcher


def test_koerber_strict_matching():
    matcher = ApplicationMatcher(
        company_threshold=0.85,
        job_threshold=0.75,
        composite_threshold=0.80
    )

    apps_cache = [
        {
            "id": "app_1",
            "company_name": "Körber",
            "job_title": "Support Consultant WCS",
            "is_active": True
        },
        {
            "id": "app_2",
            "company_name": "Körber",
            "job_title": "Absolventen SAP",
            "is_active": True
        }
    ]

    # Test 1: Exact new job title - Karriere SAP should not match Absolventen SAP
    match = matcher.find_existing_application(
        company_name="Körber",
        job_title="Karriere SAP",
        thread_id="19d62fc9",
        apps_cache=apps_cache
    )
    assert match is None, f"Expected no match, but got {match}"

    # Test 2: Fuzzy match existing - Same job with slightly different text length
    match = matcher.find_existing_application(
        company_name="Körber AG",
        job_title="Support Consultant WCS",
        thread_id="some_new_thread",
        apps_cache=apps_cache
    )
    assert match is not None, "Expected match due to fuzzy job match"
    assert match["id"] == "app_1"

    # Test 3: Thread guess (but different job should fail)
    match = matcher.find_existing_application(
        company_name="Körber",
        job_title="Data Scientist",
        thread_id="some_new_thread", # Not in cache anyway
        apps_cache=apps_cache
    )
    assert match is None

    # Let's add thread_id to app_2 cache
    apps_cache[1]["thread_ids"] = ["19d392ac", "19d393be"]

    # Test 4: Same thread id, but totally different job
    match = matcher.find_existing_application(
        company_name="Körber",
        job_title="Software Engineer",
        thread_id="19d392ac",
        apps_cache=apps_cache
    )
    assert match is None, "Should not match even with same thread ID if job title is different"

