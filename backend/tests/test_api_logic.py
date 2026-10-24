import os
import sys
from pathlib import Path

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "ci-test-placeholder-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from main import fallback_outcome, validate_uuid


def test_valid_uuid_is_normalized():
    value = "A1B2C3D4-1234-4567-8901-abcdef123456"
    assert validate_uuid(value) == value.lower()


def test_invalid_call_id_returns_422():
    with pytest.raises(HTTPException) as exc:
        validate_uuid("1")
    assert exc.value.status_code == 422


@pytest.mark.parametrize(("key", "expected"), [
    ("whatsapp", "agreed_to_receive_report"),
    ("email", "agreed_to_receive_report"),
    ("callback_time", "follow_up"),
    ("call_time", "follow_up"),
    ("referral", "follow_up"),
    ("wrong_person", "wrong_person"),
    ("moved_company", "moved_company"),
    ("not_interested", "not_interested"),
])
def test_fallback_rules(key, expected):
    assert fallback_outcome([{"happened_key": key}]) == expected


def test_fallback_defaults_to_not_logged():
    assert fallback_outcome([]) == "not_logged"
