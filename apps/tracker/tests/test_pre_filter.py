import pytest
from pre_filter import apply_pre_filters
from models import EmailMetadata

def test_apply_pre_filters(mock_emails):
    # Setup - mock_emails has 3 emails, 1 generic, 2 application related.
    
    filtered_emails, stats = apply_pre_filters(mock_emails)
    
    # Assert
    assert hasattr(stats, "total")
