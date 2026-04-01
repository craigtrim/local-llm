from local_llm.archive import validate_archive


def _valid_archive():
    return {
        "title": "Test chat",
        "created_at": "2026-04-01T16:30:00+00:00",
        "archived_at": "2026-04-01T17:00:00+00:00",
        "model": "qwen2.5:7b",
        "client_ip": "192.168.4.42",
        "user_agent": "Mozilla/5.0 TestBrowser",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant.", "timestamp": "2026-04-01T16:30:00+00:00"},
            {"role": "user", "content": "Hello", "timestamp": "2026-04-01T16:30:05+00:00"},
            {"role": "assistant", "content": "Hi there!", "timestamp": "2026-04-01T16:30:07+00:00"},
        ],
    }


def test_valid_archive():
    assert validate_archive(_valid_archive()) == []


def test_valid_archive_null_title():
    data = _valid_archive()
    data["title"] = None
    assert validate_archive(data) == []


def test_allows_null_client_ip():
    data = _valid_archive()
    data["client_ip"] = None
    assert validate_archive(data) == []


def test_allows_null_user_agent():
    data = _valid_archive()
    data["user_agent"] = None
    assert validate_archive(data) == []


def test_rejects_bare_list():
    data = [{"role": "user", "content": "hi"}]
    errors = validate_archive(data, "old.json")
    assert len(errors) == 1
    assert "expected dict, got list" in errors[0]
    assert "old.json" in errors[0]


def test_rejects_missing_messages_key():
    errors = validate_archive({"title": "x", "created_at": "t", "archived_at": "t", "model": "m", "client_ip": None, "user_agent": None})
    assert any("missing 'messages' key" in e for e in errors)


def test_rejects_missing_title_key():
    data = _valid_archive()
    del data["title"]
    errors = validate_archive(data)
    assert any("missing 'title' key" in e for e in errors)


def test_rejects_non_list_messages():
    data = _valid_archive()
    data["messages"] = "bad"
    errors = validate_archive(data)
    assert any("'messages' must be a list" in e for e in errors)


def test_rejects_invalid_role():
    data = _valid_archive()
    data["messages"].append({"role": "bot", "content": "oops", "timestamp": "2026-04-01T16:31:00+00:00"})
    errors = validate_archive(data)
    assert any("invalid role 'bot'" in e for e in errors)


def test_rejects_missing_content():
    data = _valid_archive()
    data["messages"] = [{"role": "user", "timestamp": "2026-04-01T16:30:05+00:00"}]
    errors = validate_archive(data)
    assert any("missing 'content' key" in e for e in errors)


def test_rejects_non_string_content():
    data = _valid_archive()
    data["messages"] = [{"role": "user", "content": 123, "timestamp": "2026-04-01T16:30:05+00:00"}]
    errors = validate_archive(data)
    assert any("'content' must be a string" in e for e in errors)


def test_rejects_non_string_title():
    data = _valid_archive()
    data["title"] = 42
    errors = validate_archive(data)
    assert any("'title' must be a string or null" in e for e in errors)


def test_rejects_empty_conversation():
    data = _valid_archive()
    data["messages"] = [{"role": "system", "content": "You are helpful.", "timestamp": "2026-04-01T16:30:00+00:00"}]
    errors = validate_archive(data)
    assert any("no user or assistant messages" in e for e in errors)


def test_rejects_missing_created_at():
    data = _valid_archive()
    del data["created_at"]
    errors = validate_archive(data)
    assert any("missing 'created_at' key" in e for e in errors)


def test_rejects_missing_archived_at():
    data = _valid_archive()
    del data["archived_at"]
    errors = validate_archive(data)
    assert any("missing 'archived_at' key" in e for e in errors)


def test_rejects_missing_model():
    data = _valid_archive()
    del data["model"]
    errors = validate_archive(data)
    assert any("missing 'model' key" in e for e in errors)


def test_rejects_missing_client_ip_key():
    data = _valid_archive()
    del data["client_ip"]
    errors = validate_archive(data)
    assert any("missing 'client_ip' key" in e for e in errors)


def test_rejects_missing_user_agent_key():
    data = _valid_archive()
    del data["user_agent"]
    errors = validate_archive(data)
    assert any("missing 'user_agent' key" in e for e in errors)


def test_rejects_message_without_timestamp():
    data = _valid_archive()
    data["messages"] = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello", "timestamp": "2026-04-01T16:30:07+00:00"},
    ]
    errors = validate_archive(data)
    assert any("missing 'timestamp' key" in e for e in errors)


def test_collects_multiple_errors():
    data = {
        "title": 42,
        "messages": [
            {"role": "bot", "content": 123, "timestamp": "t"},
            {"role": "user", "timestamp": "t"},
        ],
    }
    errors = validate_archive(data, "bad.json")
    # title error + missing metadata keys + invalid role + non-string content + missing content
    assert len(errors) >= 4
    assert all("bad.json" in e for e in errors)
