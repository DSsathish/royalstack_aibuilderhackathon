from app.services import conversation, db, sessions


def test_turns_are_saved_and_loaded_in_order(store_id):
    s = sessions.create(store_id, "instore")
    conversation.add_turn(s, "user", "Where is atta?")
    conversation.add_turn(s, "assistant", "Aisle A1, bay 2.")
    conversation.add_turn(s, "user", "Add two")
    turns = conversation.recent(s, limit=10)
    assert [(t["role"], t["text"]) for t in turns] == [("user", "Where is atta?"), ("assistant", "Aisle A1, bay 2."), ("user", "Add two")]


def test_recent_returns_only_the_last_n(store_id):
    s = sessions.create(store_id, "online")
    for i in range(8):
        conversation.add_turn(s, "user", f"q{i}")
    assert [t["text"] for t in conversation.recent(s, limit=3)] == ["q5", "q6", "q7"]


def test_owner_memory_is_keyed_by_user_across_sessions(store_id):
    a = sessions.create(store_id, "owner", user_id="owner-9")
    b = sessions.create(store_id, "owner", user_id="owner-9")
    conversation.add_turn(a, "user", "What is running low?")
    assert conversation.recent(b, limit=5)[0]["text"] == "What is running low?"
    other = sessions.create(store_id, "owner", user_id="owner-10")
    assert conversation.recent(other, limit=5) == []


def test_shopper_memory_is_per_session(store_id):
    a = sessions.create(store_id, "instore")
    b = sessions.create(store_id, "instore")
    conversation.add_turn(a, "user", "milk")
    assert conversation.recent(b, limit=5) == []


def test_history_text_is_compact_and_bounded(store_id):
    s = sessions.create(store_id, "instore")
    conversation.add_turn(s, "user", "x" * 2000)
    conversation.add_turn(s, "assistant", "y" * 2000)
    text = conversation.history_text(s)
    assert text.startswith("Earlier in this conversation")
    assert "Shopper: " in text and "Assistant: " in text
    assert len(text) < 1200          # each turn truncated
    assert conversation.history_text(sessions.create(store_id, "instore")) == ""


def test_empty_and_whitespace_turns_are_ignored(store_id):
    s = sessions.create(store_id, "instore")
    conversation.add_turn(s, "user", "   ")
    conversation.add_turn(s, "assistant", "")
    assert conversation.recent(s, limit=5) == []
