"""BASE FILE - stable entry point the oracle exercises."""
import consumer
import producer


def account_report(handle):
    return consumer.render(handle)
