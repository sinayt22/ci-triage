from pydantic import ValidationError
import pytest
from unittest.mock import patch, MagicMock
from schema import Candidate, DiffInfo, DiffStatus, EvalCase, LogInfo, RunInfo, StepsInfo, TriageInfo, candidate_to_eval_case
import triage
 
 
def _with_mocked_response(text):
    mock_provider = MagicMock()
    mock_provider.complete.return_value = text
    return patch("triage._get_provider", return_value=mock_provider)
 
def _case(log="some log", **kw):
    return EvalCase(id="t", repo="r", log_excerpt=log, 
                    diff_summary=None, label="unknown", **kw)

def test_valid_json_extracts_label():
    with _with_mocked_response('{"label": "flaky-test", "reasoning": "unrelated to diff, timing-based"}'):
        assert triage.classify(_case()) == "flaky-test"
 
 
def test_model_returned_unknown_is_a_real_label_not_an_error():
    # The model looking at the log and genuinely not knowing is a valid
    # judgment call - it must NOT be treated the same as a parse failure.
    with _with_mocked_response('{"label": "unknown", "reasoning": "not enough information in the log"}'):
        assert triage.classify(_case()) == "unknown"
 
 
def test_malformed_json_raises_parse_error():
    with _with_mocked_response("Sure! The label is flaky-test because..."):
        with pytest.raises(triage.ClassificationParseError):
            triage.classify(_case())
 
 
def test_invalid_label_raises_parse_error():
    with _with_mocked_response('{"label": "totally-made-up-label", "reasoning": "oops"}'):
        with pytest.raises(triage.ClassificationParseError):
            triage.classify(_case())

def test_render_includes_all_models_visible_fields():
    case = _case(
        log="LOG_SENTINEL",
        failed_step_name="STEP_SENTINEL",
        workflow_config="CONFIG_SENTINEL",
        run_attempt = 3,
        event = "EVENT_SENTINEL",
        head_branch = "BRANCH_SENTINEL"
    )
    rendered = triage.render_case(case)
    for sentinel in ["LOG_SENTINEL", "STEP_SENTINEL", "CONFIG_SENTINEL", "3", 
                     "EVENT_SENTINEL", "BRANCH_SENTINEL"]:
        assert sentinel in rendered

def test_absent_fields_render_as_not_provided():
    case = _case(log="some log")
    rendered = triage.render_case(case)
    assert "None" not in rendered
    assert "(not provided) in rendered"

def test_candidate_to_eval_maps_every_field():
    c = Candidate(
        id="i", repo="r", job_url="job url", job_name="job name",
        run=RunInfo(run_id=1, run_attempt=2, event="schedule", head_branch="main"),
        steps=StepsInfo(failed_step_name="Autobuild", failed_step_number=1),
        log=LogInfo(excerpt="LOG", excerpt_strategy="tail-150"),
        diff=DiffInfo(summary="DIFF", status=DiffStatus.OK),
        workflow_config="YAML"
    )
    case = candidate_to_eval_case(c, label="config-error", notes="n")
    assert case.log_excerpt == "LOG"
    assert case.diff_summary == "DIFF"
    assert case.event == "schedule"
    assert case.failed_step_name == "Autobuild"
    assert case.id == "i"
    assert case.repo == "r"
    assert case.workflow_config == "YAML"
    assert case.head_branch == "main"
    assert case.notes == "n"
    assert case.run_attempt == 2

