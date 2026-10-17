import io

import joblib
import numpy as np
import pandas as pd
import pytest

from app.ml import ModelUnavailable, S3ModelRegistry, make_features, prepare


class FakeS3:
    def __init__(self, objects=None):
        self.objects = objects or {}
        self.calls = 0

    def get_object(self, Bucket, Key):
        self.calls += 1
        if Key not in self.objects:
            raise FakeNoSuchKey()
        return {"Body": io.BytesIO(self.objects[Key])}


class FakeNoSuchKey(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "NoSuchKey"}}


class DummyModel:
    def predict(self, frame):
        return np.array([12.5])


def bundle_bytes():
    stream = io.BytesIO()
    joblib.dump({"model": DummyModel(), "version": "test-v1", "target": "pm25"}, stream)
    return stream.getvalue()


def test_loads_model_from_stable_slug_and_caches_it():
    s3 = FakeS3({"models/latest/new-delhi_pm25.joblib": bundle_bytes()})
    registry = S3ModelRegistry(bucket="model-bucket", s3_client=s3)
    assert registry.get("new-delhi", "pm25")["version"] == "test-v1"
    assert registry.get("new-delhi", "pm25")["version"] == "test-v1"
    assert s3.calls == 1


def test_missing_model_is_unavailable_and_negative_cached():
    s3 = FakeS3()
    registry = S3ModelRegistry(bucket="model-bucket", negative_ttl_seconds=60, s3_client=s3)
    with pytest.raises(ModelUnavailable):
        registry.get("new-delhi", "pm25")
    with pytest.raises(ModelUnavailable):
        registry.get("new-delhi", "pm25")
    assert s3.calls == 1


def test_rejects_unstable_slug_and_unknown_target():
    registry = S3ModelRegistry(bucket="model-bucket", s3_client=FakeS3())
    with pytest.raises(ValueError):
        registry.get("New Delhi", "pm25")
    with pytest.raises(ValueError):
        registry.get("new-delhi", "ozone")


def test_dynamic_version_resolution_from_pointer():
    s3 = FakeS3({
        "models/LATEST_VERSION": b"202610171600",
        "models/202610171600/new-delhi_pm25.joblib": bundle_bytes(),
    })
    registry = S3ModelRegistry(bucket="model-bucket", s3_client=s3, auto_resolve=True)
    assert registry.active_version == "202610171600"
    model = registry.get("new-delhi", "pm25")
    assert model["version"] == "test-v1"


def test_hot_reload_clears_cache_and_switches_version():
    stream1 = io.BytesIO()
    joblib.dump({"model": DummyModel(), "version": "v1", "target": "pm25"}, stream1)
    stream2 = io.BytesIO()
    joblib.dump({"model": DummyModel(), "version": "v2", "target": "pm25"}, stream2)

    s3_objects = {
        "models/LATEST_VERSION": b"202610171000",
        "models/202610171000/delhi_pm25.joblib": stream1.getvalue(),
        "models/202610171200/delhi_pm25.joblib": stream2.getvalue(),
    }
    s3 = FakeS3(s3_objects)
    registry = S3ModelRegistry(bucket="model-bucket", s3_client=s3, auto_resolve=True)
    assert registry.active_version == "202610171000"
    assert registry.get("delhi", "pm25")["version"] == "v1"

    # Colab updates LATEST_VERSION on S3
    s3_objects["models/LATEST_VERSION"] = b"202610171200"

    # Trigger hot-reload
    reload_result = registry.reload()
    assert reload_result["previous_version"] == "202610171000"
    assert reload_result["active_version"] == "202610171200"
    assert registry.get("delhi", "pm25")["version"] == "v2"



def test_prepare_and_features_are_hourly():
    frame = pd.DataFrame({
        "observed_at": pd.date_range("2026-01-01", periods=48, freq="h", tz="UTC"),
        "pm25": np.arange(48, dtype=float),
        "pm10": np.arange(48, dtype=float) + 2,
        "temperature": np.ones(48), "humidity": np.ones(48) * 50,
        "wind_speed": np.ones(48) * 3,
    })
    prepared = prepare(frame)
    features = make_features(prepared, "pm25")
    assert len(prepared) == 48
    assert list(features.columns)[0] == "lag_1"
    assert features.iloc[-1].notna().all()
