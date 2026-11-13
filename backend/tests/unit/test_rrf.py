"""Ví dụ rank biết đáp án; không dùng query/qrels validation hoặc test."""

from dataclasses import replace

import pytest

from app.search.rrf import CLIP_SOURCE, E5_SOURCE, RRFConfig, reciprocal_rank_fusion


@pytest.fixture
def config():
    return RRFConfig(rank_constant=60, clip_candidate_limit=200,
                     e5_candidate_limit=200, cutoff=10)


def test_known_answer_missing_stream_contributes_zero_and_provenance_is_exact(config):
    result = reciprocal_rank_fusion(["a", "b", "c"], ["b", "d", "a"], config=config)
    assert [hit.asset_id for hit in result.hits] == ["b", "a", "d", "c"]
    b, a, d, c = result.hits
    assert b.score == pytest.approx(1 / 62 + 1 / 61)
    assert a.score == pytest.approx(1 / 61 + 1 / 63)
    assert d.score == pytest.approx(1 / 62)
    assert c.score == pytest.approx(1 / 63)
    assert [(p.source, p.rank) for p in b.contributions] == [(CLIP_SOURCE, 2), (E5_SOURCE, 1)]
    assert [(p.source, p.rank) for p in d.contributions] == [(E5_SOURCE, 2)]
    assert sum(p.contribution for p in b.contributions) == pytest.approx(b.score)
    assert result.config_version == config.config_version


def test_tie_break_is_asset_id_order_even_at_final_cutoff(config):
    config = replace(config, cutoff=1)
    result = reciprocal_rank_fusion(["z", "a"], ["a", "z"], config=config)
    assert [hit.asset_id for hit in result.hits] == ["a"]
    assert result.hits[0].score == pytest.approx(1 / 61 + 1 / 62)


def test_duplicate_ids_do_not_consume_candidate_slots_or_contribute_twice(config):
    config = replace(config, clip_candidate_limit=2, e5_candidate_limit=1)
    clip, e5 = ["a", "a", "b", "c"], ["b", "b", "c"]
    result = reciprocal_rank_fusion(clip, e5, config=config)
    assert [hit.asset_id for hit in result.hits] == ["b", "a"]
    assert result.hits[0].score == pytest.approx(1 / 62 + 1 / 61)
    assert [(p.source, p.rank) for p in result.hits[0].contributions] == [
        (CLIP_SOURCE, 2), (E5_SOURCE, 1)]
    assert clip == ["a", "a", "b", "c"]
    assert e5 == ["b", "b", "c"]


def test_candidate_limits_are_applied_to_each_stream_before_fusion(config):
    config = replace(config, clip_candidate_limit=1, e5_candidate_limit=1)
    result = reciprocal_rank_fusion(["a", "b"], ["b", "a"], config=config)
    assert [hit.asset_id for hit in result.hits] == ["a", "b"]
    assert all(len(hit.contributions) == 1 for hit in result.hits)


@pytest.mark.parametrize("clip,e5,source", [(["b", "a"], [], CLIP_SOURCE),
                                          ([], ["b", "a"], E5_SOURCE)])
def test_one_empty_stream_preserves_other_ranking(config, clip, e5, source):
    result = reciprocal_rank_fusion(clip, e5, config=config)
    assert [hit.asset_id for hit in result.hits] == ["b", "a"]
    assert [hit.contributions[0].source for hit in result.hits] == [source, source]


def test_empty_result_still_identifies_configuration(config):
    result = reciprocal_rank_fusion([], [], config=config)
    assert result.hits == ()
    assert result.config_version == config.config_version


def test_rrf_score_is_not_clipped_to_cosine_range(config):
    result = reciprocal_rank_fusion(["a"], ["a"], config=replace(config, rank_constant=0))
    assert result.hits[0].score == 2.0


@pytest.mark.parametrize("field,value", [("rank_constant", 0), ("rank_constant", 10),
    ("clip_candidate_limit", 100), ("e5_candidate_limit", 100), ("cutoff", 5)])
def test_every_effective_parameter_changes_version(config, field, value):
    changed = replace(config, **{field: value})
    assert changed.config_version != config.config_version
    assert changed.parameters()[field] == value


def test_parameter_version_is_deterministic_and_policy_is_explicit(config):
    other = RRFConfig(cutoff=10, e5_candidate_limit=200, clip_candidate_limit=200, rank_constant=60)
    assert other.config_version == config.config_version
    assert config.parameters()["rank_origin"] == 1
    assert config.parameters()["weights"] == [1, 1]
    assert config.parameters()["missing_source_contribution"] == 0


@pytest.mark.parametrize("field", ["rank_constant", "clip_candidate_limit", "e5_candidate_limit", "cutoff"])
@pytest.mark.parametrize("value", [True, 1.0, "10", None, -1])
def test_invalid_config_types_or_negative_values_rejected(config, field, value):
    with pytest.raises(ValueError):
        replace(config, **{field: value})


@pytest.mark.parametrize("field", ["clip_candidate_limit", "e5_candidate_limit", "cutoff"])
@pytest.mark.parametrize("value", [0, 201])
def test_candidate_limits_and_cutoff_are_bounded_to_experiment(config, field, value):
    with pytest.raises(ValueError):
        replace(config, **{field: value})


@pytest.mark.parametrize("asset_id", [None, 1, "", " a", "a ", ".", "..", "a/b", "a\\b", "a?b", "a#b", "a%b", "x" * 129])
def test_malformed_ids_are_not_silently_dropped(config, asset_id):
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([asset_id], [], config=config)


@pytest.mark.parametrize("stream", ["asset", b"asset", {"asset"}, None])
def test_unordered_or_scalar_stream_is_rejected(config, stream):
    with pytest.raises(TypeError):
        reciprocal_rank_fusion(stream, [], config=config)


def test_invalid_id_beyond_candidate_limit_is_not_hidden(config):
    with pytest.raises(ValueError):
        reciprocal_rank_fusion(["ok", "bad/id"], [], config=replace(config, clip_candidate_limit=1))
