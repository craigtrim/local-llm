from local_llm.archive import validate_archive


def _valid_archive():
    return {
        "title": "Test chat",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
    }


def test_valid_archive():
    assert validate_archive(_valid_archive()) == []


def test_valid_archive_null_title():
    data = _valid_archive()
    data["title"] = None
    assert validate_archive(data) == []


def test_rejects_bare_list():
    data = [{"role": "user", "content": "hi"}]
    errors = validate_archive(data, "old.json")
    assert len(errors) == 1
    assert "expected dict, got list" in errors[0]
    assert "old.json" in errors[0]


def test_rejects_missing_messages_key():
    errors = validate_archive({"title": "x"})
    assert any("missing 'messages' key" in e for e in errors)


def test_rejects_missing_title_key():
    data = {"messages": [{"role": "user", "content": "hi"}]}
    errors = validate_archive(data)
    assert any("missing 'title' key" in e for e in errors)


def test_rejects_non_list_messages():
    errors = validate_archive({"title": "x", "messages": "bad"})
    assert any("'messages' must be a list" in e for e in errors)


def test_rejects_invalid_role():
    data = _valid_archive()
    data["messages"].append({"role": "bot", "content": "oops"})
    errors = validate_archive(data)
    assert any("invalid role 'bot'" in e for e in errors)


def test_rejects_missing_content():
    data = {
        "title": "x",
        "messages": [{"role": "user"}],
    }
    errors = validate_archive(data)
    assert any("missing 'content' key" in e for e in errors)


def test_rejects_non_string_content():
    data = {
        "title": "x",
        "messages": [{"role": "user", "content": 123}],
    }
    errors = validate_archive(data)
    assert any("'content' must be a string" in e for e in errors)


def test_rejects_non_string_title():
    data = _valid_archive()
    data["title"] = 42
    errors = validate_archive(data)
    assert any("'title' must be a string or null" in e for e in errors)


def test_rejects_empty_conversation():
    data = {
        "title": None,
        "messages": [{"role": "system", "content": "You are helpful."}],
    }
    errors = validate_archive(data)
    assert any("no user or assistant messages" in e for e in errors)


def test_collects_multiple_errors():
    data = {
        "title": 42,
        "messages": [
            {"role": "bot", "content": 123},
            {"role": "user"},
        ],
    }
    errors = validate_archive(data, "bad.json")
    # title error + invalid role + non-string content + missing content + no user/assistant
    assert len(errors) >= 4
    assert all("bad.json" in e for e in errors)
