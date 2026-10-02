import reader
import state


def put(key, value):
    state.values[key] = value
    reader.invalidate(key)


def update_many(items):
    for key, value in items.items():
        put(key, value)
