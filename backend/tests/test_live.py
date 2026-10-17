import pytest
from fastapi.testclient import TestClient

from app.agent import live
from app.domain.models import Inventory, Product, Store
from app.main import app
from app.services import catalog, db


def test_declarations_match_mode_tools():
    decls = live.declarations("instore")
    names = {d.name for d in decls}
    assert "navigate_to" in names and "add_to_cart" not in names and "get_low_stock" not in names
    decls = live.declarations("online")
    add = next(d for d in decls if d.name == "add_to_cart")
    props = add.parameters.properties
    assert "tool_context" not in props
    assert props["product_id"].type.name == "STRING" and props["qty"].type.name == "INTEGER"
    assert set(add.parameters.required) == {"product_id", "qty"}
    search = next(d for d in decls if d.name == "search_products")
    assert "max_results" not in search.parameters.required
    assert "Tamil" in search.description


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    p = Product.from_row(store_id=store_id, sku="milk", name="Toned Milk", price=28, mrp=28, threshold=500, tags=["milk"])
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=3).model_dump())
    catalog.invalidate(store_id)
    return store_id


def test_dispatch_runs_tool_with_state(shop):
    out = live.dispatch("search_products", {"query": "milk"}, {"store_id": shop, "mode": "instore", "cart_id": f"{shop}-c"})
    assert out["products"][0]["name"] == "Toned Milk" and out["signal"] == "found"


def test_dispatch_unknown_tool(shop):
    assert live.dispatch("rm_rf", {}, {"store_id": shop, "mode": "instore"}) == {"error": "unknown_tool"}


def test_dispatch_mode_gated(shop):
    assert live.dispatch("get_low_stock", {}, {"store_id": shop, "mode": "instore"}) == {"error": "unknown_tool"}


def test_websocket_rejects_bad_session():
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/agent/live?session_id=nope") as ws:
            ws.receive_text()


def test_websocket_accepts_owner_session_from_owner_endpoint_outside_dev(store_id, monkeypatch):
    import json
    from app.api import agent as agent_api
    from app.config import settings
    from app.domain.models import Store
    from app.services import sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    owner_s = sessions.create(store_id, "owner", user_id="owner-1")       # as /owner/{id}/session does
    dev_s = sessions.create(store_id, "owner")                            # as the dev /sessions path does
    monkeypatch.setattr(settings, "env", "demo")

    async def fake_run(ws, s):
        await ws.send_text(json.dumps({"type": "ready", "mode": s.mode}))
    monkeypatch.setattr(agent_api.live, "run", fake_run)
    client = TestClient(app)
    with client.websocket_connect(f"/agent/live?session_id={owner_s.session_id}") as ws:
        assert json.loads(ws.receive_text())["mode"] == "owner"
    with pytest.raises(Exception):
        with client.websocket_connect(f"/agent/live?session_id={dev_s.session_id}") as ws:
            ws.receive_text()


def test_live_config_has_voice_vad_resumption_compression_and_history(store_id):
    from google.genai import types
    from app.domain.models import Store
    from app.services import conversation, sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    s = sessions.create(store_id, "instore")
    conversation.add_turn(s, "user", "Do you have basmati rice?")
    cfg = live._config(s)
    assert cfg.speech_config.voice_config.prebuilt_voice_config.voice_name == "Kore"
    vad = cfg.realtime_input_config.automatic_activity_detection
    assert vad.silence_duration_ms == 1100 and vad.prefix_padding_ms == 400
    assert vad.end_of_speech_sensitivity == types.EndSensitivity.END_SENSITIVITY_LOW
    assert cfg.session_resumption is not None and cfg.context_window_compression is not None
    assert cfg.enable_affective_dialog is True
    assert "basmati rice" in cfg.system_instruction and "ask the shopper to repeat" in cfg.system_instruction
    assert "navigate_to" in {d.name for d in cfg.tools[0].function_declarations}


def test_config_reuses_a_stored_resumption_handle(store_id):
    from app.domain.models import Store
    from app.services import sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    s = sessions.create(store_id, "instore")
    live._resume_handles[s.session_id] = "abc123"
    assert live._config(s).session_resumption.handle == "abc123"
    live._resume_handles.pop(s.session_id, None)
    assert live._config(s).session_resumption.handle is None


def test_turn_recorder_saves_on_turn_complete_and_interruption():
    saved = []
    rec = live.TurnRecorder(lambda role, text: saved.append((role, text)))
    rec.user("where is "); rec.user("atta?")
    rec.assistant("Aisle A1, "); rec.assistant("bay 2.")
    rec.turn_complete()
    assert saved == [("user", "where is atta?"), ("assistant", "Aisle A1, bay 2.")]
    rec.assistant("The price is"); rec.interrupted()
    assert saved[-1] == ("assistant", "The price is [interrupted]")   # memory must not claim the rest was said
    rec.turn_complete()
    assert len(saved) == 3           # nothing new to save


def test_search_in_store_also_highlights_the_top_product_on_the_map():
    result = {"products": [{"product_id": "p1", "name": "Atta", "aisle": "A1", "bay": 2}, {"product_id": "p2", "name": "Rice", "aisle": "A1", "bay": 3}], "signal": "found"}
    extra = live.extra_actions("search_products", result, {"mode": "instore"})
    assert extra == [{"type": "action", "name": "highlight_map", "data": {"aisle": "A1", "bay": 2, "product_id": "p1", "name": "Atta", "shelf": 1, "side": "left", "x": 0, "y": 0}}]
    assert live.extra_actions("search_products", result, {"mode": "online"}) == []
    assert live.extra_actions("search_products", {"products": [], "signal": "not_carried"}, {"mode": "instore"}) == []
    assert live.extra_actions("get_product", result, {"mode": "instore"}) == []


def test_dispatch_coerces_string_numbers(monkeypatch):
    from app.agent import tools
    seen = {}
    def fake_add(product_id: str, qty: int, tool_context) -> dict:
        seen.update(product_id=product_id, qty=qty)
        return {"ok": True}
    monkeypatch.setitem(live.TOOLS_BY_MODE, "online", [fake_add])
    fake_add.__name__ = "fake_add"
    assert live.dispatch("fake_add", {"product_id": "x", "qty": "2"}, {"mode": "online"}) == {"ok": True}
    assert seen == {"product_id": "x", "qty": 2}


def test_live_client_prefers_ai_studio_when_a_live_key_is_set(monkeypatch):
    from app.config import settings
    from app.services import gemini
    sentinel = object()
    monkeypatch.setattr(gemini, "client", lambda: sentinel)
    monkeypatch.setattr(settings, "gemini_live_api_key", "")
    assert gemini.live_client() is sentinel                       # no live key: the shared (Vertex) client
    monkeypatch.setattr(settings, "gemini_live_api_key", "test-key")
    c = gemini.live_client()
    assert c is not sentinel and not c.vertexai


def test_affective_dialog_is_a_setting(monkeypatch, store_id):
    from app.config import settings
    from app.domain.models import Store
    from app.services import db, sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    s = sessions.create(store_id, "online")
    assert live._config(s).enable_affective_dialog is True
    monkeypatch.setattr(settings, "gemini_live_affective", False)
    assert live._config(s).enable_affective_dialog is None


# --- echo and noise handling in the bridge -----------------------------------------------------------------------

def test_clean_drops_transcriber_noise_markers():
    assert live.clean("{background}") == ""
    assert live.clean("hello {noise} there <music>") == "hello there"
    assert live.clean("atta please") == "atta please"


def test_is_echo_matches_the_assistant_words_despite_transcriber_spelling():
    assert live.is_echo("I'm sorry. I", "I'm sorry I did not catch that")                 # the loudspeaker loop from the field
    assert live.is_echo("I'm sorry, I did not catch", "I'm sorry I")                     # transcript lagged behind the audio
    assert live.is_echo("Yes, we have Aashirvaad whole wheat atta in 5 kg for Rs 265 and 10 kg for Rs 520 and Maggi atta noodles 72 g for 18 rupees",
                        "Yes, we have Aashirvaad Whole Wheat Atta in 5kg for 265 rupees and 10kg for 520 rupees, and Maggi Atta Noodles 72g for 18 rupees.")
    assert live.is_echo("Aashirvaad whole wheat atta in 5 kg for Rs 265 and 10 kg for Rs 520",   # a leak from the middle of the reply
                        "Yes, we have Aashirvaad Whole Wheat Atta in 5kg for 265 rupees and 10kg for 520 rupees.")
    assert not live.is_echo("Aashirvaad atta 5 kg", "Yes, we have Aashirvaad atta 5 kg at 265 rupees.")   # a shopper repeating a name
    assert not live.is_echo("Add 2 packs of atta", "Added 2 packs of atta to your cart.")               # a shopper echoing the wording
    assert not live.is_echo("yes", "yes we have it")                                       # too short to judge
    assert not live.is_echo("I did not", "")


def test_cut_counter_flags_two_replies_cut_off_at_their_start():
    t = [0.0]
    c = live.CutCounter(clock=lambda: t[0])
    c.reply_started(); t[0] = 0.8
    assert c.interrupted() is False                   # one early cut could be a shopper
    c.reply_started(); t[0] = 1.5
    assert c.interrupted() is True                    # the second in a row is the loudspeaker
    c.reply_started(); t[0] = 2.2
    assert c.interrupted() is False                   # counting starts again
    c.reply_started(); t[0] = 9.0
    assert c.interrupted() is False                   # cut late in a reply: a real interruption
    c.reply_started(); t[0] = 9.5
    assert c.interrupted() is False
    c.reply_started(); c.completed(); c.reply_started(); t[0] = 10.0
    assert c.interrupted() is False                   # a completed reply resets the count


def test_recorder_drops_echo_turns_and_marks_interrupted_replies():
    saved = []
    r = live.TurnRecorder(lambda role, text: saved.append((role, text)))
    r.user("Do you have atta?"); r.assistant("Yes, we have Aashirvaad atta "); r.interrupted()
    assert saved == [("user", "Do you have atta?"), ("assistant", "Yes, we have Aashirvaad atta [interrupted]")]
    assert r.user("Yes, we") is False                 # too little to judge yet
    assert r.user(" have Aashirvaad") is True         # now a copy of the reply: echo
    assert r.echo and r.user(" atta") is False        # already flagged: no second signal
    r.assistant("I am sorry, I did not catch that."); r.turn_complete()
    assert saved[2:] == []                            # the echo turn and the reply to it stay out of memory
    assert not r.echo
    r.user("Add it"); r.assistant("Added."); r.turn_complete()
    assert saved[2:] == [("user", "Add it"), ("assistant", "Added.")]


def test_live_config_carries_the_chosen_language(monkeypatch, store_id):
    from app.domain.models import Store
    from app.services import db, sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    s = sessions.create(store_id, "online")
    assert "chose" not in live._config(s).system_instruction
    s.language = "ta"
    cfg = live._config(s)
    assert "The shopper chose Tamil" in cfg.system_instruction


def test_live_transcript_language_hints(store_id):
    from app.domain.models import Store
    from app.services import db, sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())          # languages en, ta, hi
    s = sessions.create(store_id, "online")
    assert live._config(s).input_audio_transcription.language_codes == ["ta-IN", "en-IN"]   # auto: regional language first
    s.language = "hi"
    assert live._config(s).input_audio_transcription.language_codes == ["hi-IN"]
    s.language = "te"
    assert live._config(s).input_audio_transcription.language_codes == ["te-IN"]       # any listed language, not just three
    db.store_ref(store_id).update({"languages": ["en"]})
    s.language = "auto"
    assert live._config(s).input_audio_transcription.language_codes == ["en-IN"]
