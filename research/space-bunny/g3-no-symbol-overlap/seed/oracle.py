"""Identical common oracle for base / A / B / A+B arms. No arm-specific branches."""
import app
import store


def main():
    store._data.clear()
    store._listeners.clear()
    import wiring  # noqa: F401  installs the invalidation contract
    importlib_reset = None

    # 1. single write then read
    store.write("a", 1)
    assert app.get("a") == 1, "single write must be visible to a reader"

    # 2. bulk write then read (the behaviour a cache can silently break)
    app.set_bulk({"b": 10, "c": 20})
    assert app.get("b") == 10, "bulk write b must be visible to a reader"
    assert app.get("c") == 20, "bulk write c must be visible to a reader"

    # 3. repeat bulk write with different values (stale-cache trap)
    app.set_bulk({"b": 11, "c": 21})
    assert app.get("b") == 11, "second bulk write b must be visible to a reader"
    assert app.get("c") == 21, "second bulk write c must be visible to a reader"

    # 4. mixed order: bulk then single
    store.write("d", 5)
    assert app.get("d") == 5
    app.set_bulk({"b": 12})
    assert app.get("b") == 12, "bulk after single must be visible to a reader"

    # 5. three-key bulk (catches dispatch that only handles the first/last key)
    app.set_bulk({"e": 1, "f": 2, "g": 3})
    assert app.get("e") == 1, "bulk e must be visible"
    assert app.get("f") == 2, "bulk f must be visible"
    assert app.get("g") == 3, "bulk g must be visible"

    print("common accepted behavior passed")


if __name__ == "__main__":
    main()
