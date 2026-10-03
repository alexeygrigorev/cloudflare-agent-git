"""BASE FILE - the stable public entry point the oracle exercises."""
import bulk
import cache


def get(key):
    return cache.read(key)


def set_bulk(items):
    bulk.write_bulk(items)
