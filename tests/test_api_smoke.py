import inspect

import pydjimqtt


def test_public_api_exports() -> None:
    missing = []
    non_callable = []
    allowed_values = {
        "DEFAULT_GIMBAL_PITCH_PROFILE",
        "GIMBAL_PITCH_MIN_DEG",
        "GIMBAL_PITCH_MAX_DEG",
    }

    for name in pydjimqtt.__all__:
        if not hasattr(pydjimqtt, name):
            missing.append(name)
            continue

        value = getattr(pydjimqtt, name)
        if name in allowed_values:
            continue
        if inspect.isclass(value):
            continue
        if not callable(value):
            non_callable.append(name)

    assert not missing, f"Missing exports: {missing}"
    assert not non_callable, f"Non-callable exports: {non_callable}"
