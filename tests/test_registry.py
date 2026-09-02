from findmyjob.pipelines.fetch import FetchPipeline
from findmyjob.pipelines.registry import default_pipelines


def test_fetch_only_returns_just_fetch():
    assert [p.name for p in default_pipelines(fetch_only=True)] == ["fetch"]


def test_no_llm_drops_model_stages():
    names = [p.name for p in default_pipelines(no_llm=True)]
    assert "analyze" not in names and "judge" not in names
    assert names[0] == "fetch" and names[-1] == "notify"


def test_full_sequence_is_ordered():
    assert [p.name for p in default_pipelines()] == [
        "fetch",
        "normalize",
        "enrich",
        "dedup",
        "prefilter",
        "analyze",
        "score",
        "judge",
        "decide",
        "notify",
    ]


def test_source_narrowing_flags_reach_the_fetch_pipeline():
    pipelines = default_pipelines(only_sources={"ba"}, limit_per_source=5)
    fetch = pipelines[0]
    assert isinstance(fetch, FetchPipeline)
    assert fetch._only == {"ba"}
    assert fetch._limit_per_source == 5
