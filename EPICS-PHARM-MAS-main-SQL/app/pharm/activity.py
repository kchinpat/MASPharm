"""Recent cabinet activity in plain words, for UI two's log in both the desktop
and the browser. Only what happened to the stock is shown: sign-ins, sessions
and the steps within an operation stay in the exported audit."""
from datetime import datetime, timedelta
import json
import re

# The events worth a line, each the outcome of an operation.
SHOWN = ("committed", "reconciled", "reconciliation", "cancelled", "explicit_reopen_requested")
INTERRUPTED = {"dispense": "Dispensing from drawer {}", "load": "Loading drawer {}", "unload": "Emptying drawer {}"}


def plural(unit, count):
    """'bottle' -> 'bottles', 'blister pack' -> 'blister packs'; leaves abbreviations such as 'mL' alone."""
    unit = (unit or "").strip()
    if count == 1 or not unit.replace(" ", "").isalpha() or not unit.islower() or unit.endswith("s"):
        return unit
    return unit + ("es" if unit.endswith(("x", "ch", "sh")) else "s")


def capitalized(name):
    """A catalog name, which may be all lower case, with a capital to start."""
    return name[:1].upper() + name[1:]


def when(stamp, now=None):
    """The local time of an event, with its day unless it was today."""
    moment = datetime.fromisoformat(stamp).astimezone()
    today = (now or datetime.now().astimezone()).date()
    clock = moment.strftime("%H:%M")
    if moment.date() == today:
        return clock
    if moment.date() == today - timedelta(days=1):
        return f"Yesterday {clock}"
    return f"{moment.day} {moment:%b} {clock}"


def describe(event, now=None):
    """One event joined with its operation, as {when, text, attention}.
    `attention` marks a drawer that still needs a count."""
    product = json.loads(event["product"] or "{}")
    drawer, kind, action = event["compartment"], event["kind"], event["action"]
    name = capitalized(product.get("generic_name", ""))

    def amount(count):
        return f"{count} {plural(product.get('unit') or 'unit', count)}" + (f" of {name}" if name else "")
    if action == "committed":
        count = event["requested"]
        text = {"dispense": f"Dispensed {amount(count)} from drawer {drawer}",
                "load": f"Loaded {amount(count)} into drawer {drawer}",
                "unload": f"Emptied drawer {drawer} ({amount(count)})"}[kind]
    elif action == "reconciled":
        found = re.match(r"Remaining count (\d+)", event["detail"])
        left = int(found[1]) if found else None
        text = f"Counted drawer {drawer}: " + ("empty" if left == 0 else amount(left) if left is not None else "saved")
    elif action == "reconciliation":
        text = (f"Drawer {drawer} was unlocked by hand ({event['reason']}). It needs a count." if kind == "manual"
                else f"{INTERRUPTED[kind].format(drawer)} was interrupted. It needs a count.")
    elif action == "cancelled":
        text = f"Drawer {drawer} did not unlock, so nothing changed"
    else:
        text = f"Drawer {drawer} unlocked again"
    return {"when": when(event["time"], now), "text": text,
            "attention": action == "reconciliation" and event["state"] == "reconciliation"}


def recent(store, limit=3, now=None):
    """The newest lines, newest first."""
    return [describe(event, now) for event in store.recent_events(SHOWN, limit)]
