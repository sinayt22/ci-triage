import pytest
from unittest.mock import patch, MagicMock
import triage
 
 
def _with_mocked_response(text):
    mock_provider = MagicMock()
    mock_provider.complete.return_value = text
    return patch("triage._get_provider", return_value=mock_provider)
 
 
def test_valid_json_extracts_label():
    with _with_mocked_response('{"label": "flaky-test", "reasoning": "unrelated to diff, timing-based"}'):
        assert triage.classify("some log", "some diff") == "flaky-test"
 
 
def test_model_returned_unknown_is_a_real_label_not_an_error():
    # The model looking at the log and genuinely not knowing is a valid
    # judgment call - it must NOT be treated the same as a parse failure.
    with _with_mocked_response('{"label": "unknown", "reasoning": "not enough information in the log"}'):
        assert triage.classify("some log", "some diff") == "unknown"
 
 
def test_malformed_json_raises_parse_error():
    with _with_mocked_response("Sure! The label is flaky-test because..."):
        with pytest.raises(triage.ClassificationParseError):
            triage.classify("some log", "some diff")
 
 
def test_invalid_label_raises_parse_error():
    with _with_mocked_response('{"label": "totally-made-up-label", "reasoning": "oops"}'):
        with pytest.raises(triage.ClassificationParseError):
            triage.classify("some log", "some diff")
 