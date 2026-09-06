from datetime import datetime, timedelta

import pytest

from findmyjob.models.config import AppSettings
from findmyjob.models.enums import ContractType, Decision
from findmyjob.models.job import Job, JobAnalysis
from findmyjob.services.scoring import (
    analysis_hard_checks,
    bucket,
    cheap_hard_checks,
    compute_soft_score,
)

NOW = datetime(2026, 9, 1)


def _settings(**over) -> AppSettings:
    s = AppSettings()
    for k, v in over.items():
        setattr(s, k, v)
    return s


def _job(**over) -> Job:
    base: dict = {
        "source_key": "s",
        "source_job_id": "1",
        "url": "https://x.test/1",
        "title": "Werkstudent Data Science",
        "normalized_title": "werkstudent data science",
        "company_name_raw": "Acme",
        "location_raw": "München",
        "jd_text": "Work with Python and SQL. 20h/week.",
        "posted_at": NOW - timedelta(days=3),
    }
    base.update(over)
    return Job(**base)


def _analysis(**over) -> JobAnalysis:
    a = JobAnalysis(job_id=1, analyzer_version="test")
    a.skills = [{"name": "Python", "required": True}, {"name": "SQL", "required": False}]
    a.languages = [{"lang": "German", "cefr": "B2", "required": True}]
    a.weekly_hours = 20
    a.contract_type = ContractType.WERKSTUDENT
    a.seniority = "student"
    for k, v in over.items():
        setattr(a, k, v)
    return a


# ---- cheap hard checks --------------------------------------------------
def test_cheap_checks_pass_for_a_good_job():
    assert cheap_hard_checks(_job(), _settings(), now=NOW).passed


def test_recency_fails_old_posting():
    job = _job(posted_at=NOW - timedelta(days=90))
    result = cheap_hard_checks(job, _settings(recency_days=30), now=NOW)
    assert not result.passed and "recency" in result.failures


def test_blacklist_keyword_fails():
    job = _job(title="Werkstudent Sales & Data")
    result = cheap_hard_checks(job, _settings(keywords_block=["sales"]), now=NOW)
    assert not result.passed and result.failures == ["blacklist:sales"]


def test_location_mismatch_fails_but_english_spelling_passes():
    assert cheap_hard_checks(_job(location_raw="Munich, Germany"), _settings(), now=NOW).passed
    bad = cheap_hard_checks(_job(location_raw="Hamburg"), _settings(), now=NOW)
    assert not bad.passed and "location" in bad.failures


def test_remote_job_passes_location_when_allowed():
    job = _job(location_raw="Berlin", is_remote=True)
    assert cheap_hard_checks(job, _settings(allow_remote=True), now=NOW).passed


# ---- analysis hard checks --------------------------------------------
def test_hours_hard_toggle():
    a = _analysis(weekly_hours=40)
    assert analysis_hard_checks(a, {}, _settings(hours_hard=False, hours_max=20)).passed
    failed = analysis_hard_checks(a, {}, _settings(hours_hard=True, hours_max=20))
    assert not failed.passed and "hours" in failed.failures


def test_language_hard_check_uses_profile_level():
    a = _analysis(languages=[{"lang": "German", "cefr": "C1", "required": True}])
    settings = _settings(language_hard=True, language_max_cefr="B2")
    assert not analysis_hard_checks(a, {}, settings).passed
    assert analysis_hard_checks(a, {"german": "C1"}, settings).passed  # profile covers it


def test_full_time_contract_always_fails_job_type():
    a = _analysis(contract_type="full_time")
    result = analysis_hard_checks(a, {}, _settings())
    assert not result.passed and "job_type" in result.failures


# ---- soft score -----------------------------------------------------
def test_soft_breakdown_sums_to_score():
    soft = compute_soft_score(
        job=_job(),
        analysis=_analysis(),
        profile_skills=["Python", "SQL", "dbt"],
        profile_languages={"german": "C1"},
        settings=_settings(),
        company_affinity=0.8,
        now=NOW,
    )
    total_w = sum(c["weight"] for c in soft.breakdown.values())
    weighted = sum(c["contribution"] for c in soft.breakdown.values())
    assert soft.score == pytest.approx(round(100 * weighted / total_w, 1))
    assert 0 <= soft.score <= 100


def test_skills_match_rewards_overlap():
    strong = compute_soft_score(
        job=_job(),
        analysis=_analysis(),
        profile_skills=["Python", "SQL"],
        profile_languages={"german": "C1"},
        settings=_settings(),
        company_affinity=0.5,
        now=NOW,
    )
    weak = compute_soft_score(
        job=_job(),
        analysis=_analysis(),
        profile_skills=["Photoshop"],
        profile_languages={"german": "C1"},
        settings=_settings(),
        company_affinity=0.5,
        now=NOW,
    )
    assert strong.breakdown["skills_match"]["raw"] > weak.breakdown["skills_match"]["raw"]


def test_field_relevance_ignores_job_type_word():
    """An off-field 'Werkstudent ...' must not borrow relevance from the word."""
    st = _settings(
        target_fields=["Machine Learning", "Robotics", "Data"], target_titles=["Werkstudent"]
    )
    on_field = compute_soft_score(
        job=_job(title="Werkstudent Machine Learning"),
        analysis=_analysis(
            skills=[{"name": "PyTorch", "required": True}], must_haves=["Machine Learning"]
        ),
        profile_skills=["Python"],
        profile_languages={"german": "C1"},
        settings=st,
        company_affinity=0.5,
        now=NOW,
    )
    off_field = compute_soft_score(
        job=_job(title="Immobilienmakler - Schwerpunkt Vermietung | Werkstudent"),
        analysis=_analysis(
            skills=[], must_haves=["Du bist gut organisiert.", "Du arbeitest zuverlaessig."]
        ),
        profile_skills=["Python"],
        profile_languages={"german": "C1"},
        settings=st,
        company_affinity=0.5,
        now=NOW,
    )
    assert off_field.breakdown["field_relevance"]["raw"] < 0.25
    assert (
        on_field.breakdown["field_relevance"]["raw"] > off_field.breakdown["field_relevance"]["raw"]
    )
    assert off_field.score < on_field.score


def test_hours_fit_decays_over_limit():
    over = compute_soft_score(
        job=_job(),
        analysis=_analysis(weekly_hours=30),
        profile_skills=["Python"],
        profile_languages={"german": "C1"},
        settings=_settings(hours_max=20),
        company_affinity=0.5,
        now=NOW,
    )
    assert 0 < over.breakdown["hours_fit"]["raw"] < 1


def test_zero_weight_component_contributes_nothing():
    weights = dict(AppSettings().weights)
    weights["salary_fit"] = 0
    soft = compute_soft_score(
        job=_job(),
        analysis=_analysis(),
        profile_skills=["Python"],
        profile_languages={"german": "C1"},
        settings=_settings(weights=weights),
        company_affinity=0.5,
        now=NOW,
    )
    assert soft.breakdown["salary_fit"]["contribution"] == 0


def test_bucket_thresholds():
    s = _settings(score_threshold_recommend=70, score_threshold_maybe=55)
    assert bucket(80, s) == Decision.RECOMMENDED
    assert bucket(60, s) == Decision.MAYBE
    assert bucket(40, s) == Decision.ARCHIVED
