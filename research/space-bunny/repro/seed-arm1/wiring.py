"""BASE FILE - registers the invalidation contract. No task may edit this."""
import cache
from store import register_listener

register_listener(cache.invalidate)
