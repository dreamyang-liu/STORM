import json

from judge.judge_runner import _load_resumable_leaf_results


def _write_messages(path, messages):
    path.write_text("\n".join(json.dumps(message) for message in messages) + "\n")


def test_load_resumable_leaf_results_parses_supported_score_formats(tmp_path):
    _write_messages(
        tmp_path / "leaf-zero_messages.jsonl",
        [{"role": "assistant", "content": "# Score\n\n0\n\nMissing implementation."}],
    )
    _write_messages(
        tmp_path / "leaf-one_messages.jsonl",
        [
            {"role": "user", "content": "Grade this criterion."},
            {"role": "assistant", "content": "# Score\n\n**Score: 1**\n\nImplemented."},
        ],
    )

    cached = _load_resumable_leaf_results(tmp_path)

    assert cached["leaf-zero"]["score"] == 0
    assert cached["leaf-one"]["score"] == 1
    assert cached["leaf-one"]["response"].endswith("Implemented.")


def test_load_resumable_leaf_results_skips_incomplete_transcripts(tmp_path):
    _write_messages(
        tmp_path / "no-assistant_messages.jsonl",
        [{"role": "user", "content": "The request timed out."}],
    )
    _write_messages(
        tmp_path / "no-score_messages.jsonl",
        [{"role": "assistant", "content": "I did not finish grading."}],
    )
    (tmp_path / "invalid-json_messages.jsonl").write_text("{not-json}\n")

    assert _load_resumable_leaf_results(tmp_path) == {}
    assert _load_resumable_leaf_results(None) == {}
