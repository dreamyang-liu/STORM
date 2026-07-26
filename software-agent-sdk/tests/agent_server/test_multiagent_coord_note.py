from openhands.agent_server.multiagent_sync.mgr_tools import _build_coord_note


def test_coord_note_uses_version_checks_without_intent_annotations():
    note = _build_coord_note("engineer_3")

    assert "engineer_3" in note
    assert "content + version" in note
    assert "snapshot checks" in note

    forbidden_instructions = (
        "annotate every edit",
        "intent comment",
        "preserve annotations",
        "primary coordination channel",
        "# engineer_3:",
    )
    lowered_note = note.lower()
    for instruction in forbidden_instructions:
        assert instruction.lower() not in lowered_note
