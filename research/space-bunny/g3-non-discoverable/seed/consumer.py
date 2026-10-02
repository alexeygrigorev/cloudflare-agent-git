"""Account report. TASK B owns this file only. Consumes producer's export line."""
import producer

SEPARATOR = "|"


def render(handle):
    """Render the shared account report for a handle."""
    line = producer.export_line(handle)
    fields = line.split(SEPARATOR)
    return "ACCOUNT {id} handle={handle} tier={tier}".format(
        id=fields[0], handle=fields[1], tier=fields[2]
    )
