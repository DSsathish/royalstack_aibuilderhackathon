from app.services import db, forecast


def test_put_and_get_round_trip(store_id):
    forecast.put(store_id, "p1", daily=[1.0, 2.0], avg_daily=1.5, std_daily=0.5)
    f = forecast.get(store_id, "p1")
    assert f["avg_daily"] == 1.5 and f["daily"] == [1.0, 2.0] and f["generated_at"]
    assert forecast.get(store_id, "missing") is None


def test_all_returns_dict_by_product(store_id):
    forecast.put(store_id, "a", daily=[1], avg_daily=1, std_daily=0)
    forecast.put(store_id, "b", daily=[2], avg_daily=2, std_daily=0)
    assert set(forecast.all(store_id)) == {"a", "b"}


def test_from_history_fallback_for_sparse_series():
    # fewer than 14 points: mean of what exists, std 0 when single
    out = forecast.from_history({"a": [3, 5], "b": [4]})
    assert out["a"]["avg_daily"] == 4 and out["a"]["std_daily"] == 1.0 and len(out["a"]["daily"]) == 14
    assert out["b"]["avg_daily"] == 4 and out["b"]["std_daily"] == 0


def test_from_history_zero_fills_missing_days():
    out = forecast.from_history({"a": [10.0]}, days=30)
    assert abs(out["a"]["avg_daily"] - 10 / 30) < 1e-9
