from bob_ross.server import _extract_activity_ids, _summarize_completion


def test_extract_from_single_dict():
    assert _extract_activity_ids({"id": 42, "activity_status": "queued"}) == [42]


def test_extract_from_list_of_dicts():
    assert _extract_activity_ids([{"id": 1}, {"id": 2}]) == [1, 2]


def test_extract_from_nested_activities():
    assert _extract_activity_ids({"activities": [{"id": 7}, {"id": 8}]}) == [7, 8]


def test_extract_from_activity_id_key():
    assert _extract_activity_ids({"activity_id": "99"}) == [99]


def test_extract_from_bare_int_list():
    assert _extract_activity_ids([10, 11]) == [10, 11]


def test_extract_handles_empty_and_junk():
    assert _extract_activity_ids({}) == []
    assert _extract_activity_ids({"id": True}) == []  # bool is not an id
    assert _extract_activity_ids("nope") == []


def test_summarize_all_succeeded():
    s = _summarize_completion([{"status": "succeeded"}, {"status": "succeeded"}])
    assert s["all_succeeded"] is True
    assert s["by_status"] == {"succeeded": 2}
    assert s["failures"] == []


def test_summarize_with_failure():
    s = _summarize_completion([{"status": "succeeded"}, {"status": "failed", "activity_id": 5}])
    assert s["all_succeeded"] is False
    assert s["tracked"] == 2
    assert len(s["failures"]) == 1
    assert s["failures"][0]["activity_id"] == 5
    assert s["incomplete"] == []


def test_summarize_incomplete_is_not_a_failure():
    # A timed-out activity stuck at 'delivered' is incomplete, not failed.
    s = _summarize_completion([{"status": "delivered", "timed_out": True, "activity_id": 9}])
    assert s["all_succeeded"] is False
    assert s["failures"] == []
    assert len(s["incomplete"]) == 1
    assert s["incomplete"][0]["activity_id"] == 9


def test_summarize_empty():
    assert _summarize_completion([])["all_succeeded"] is False
