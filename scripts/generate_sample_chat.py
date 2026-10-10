"""Generate the synthetic sample chat used by the demo, the tests and the README.

Nothing in the output is real. The group, the people and every message are
invented by this script. The same conversation is written twice:

    examples/sample_chat_android.txt   day first, 24-hour clock
    examples/sample_chat_iphone.txt    brackets, month first, 12-hour clock, seconds

Run it from the repository root:

    python scripts/generate_sample_chat.py

The output is the same on every run, because all randomness comes from one
seeded generator and only its random() method is used.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 42
START = date(2026, 1, 5)  # a Monday
WEEKS = 12
GROUP_OLD = "Hiking Club"
GROUP = "Hiking Club (synthetic sample)"

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
ANDROID_FILE = EXAMPLES / "sample_chat_android.txt"
IPHONE_FILE = EXAMPLES / "sample_chat_iphone.txt"

LRM = "\u200e"  # invisible mark iPhone writes before system and media text
NNBSP = "\u202f"  # narrow no-break space iPhone writes before AM/PM
OPEN_QUOTE = "\u201c"
CLOSE_QUOTE = "\u201d"

ENCRYPTION_NOTICE = (
    "Messages and calls are end-to-end encrypted. "
    "Only people in this chat can read, listen to, or share them."
)
LABEL = (
    "This is a synthetic sample chat made by scripts/generate_sample_chat.py. "
    "Every name and every message in it is invented."
)

# How talkative each fictional member is.
WEIGHTS = {"Mira": 32, "Bruno": 25, "Chen": 20, "Dalia": 15, "Tomasz": 8, "Ines": 6}
TOMASZ_JOINS = START + timedelta(days=15)
INES_JOINS = START + timedelta(days=30)
INES_LEAVES = START + timedelta(days=52)

# Relative chance of a conversation starting in each hour, 0 to 23.
HOUR_WEIGHTS = [0, 0, 0, 0, 0, 0, 1, 4, 6, 4, 2, 2, 6, 7, 3, 2, 3, 5, 9, 14, 16, 13, 7, 2]
# Conversations per day, Monday to Sunday, as (fewest, most).
THREADS_PER_DAY = [(1, 3), (1, 3), (1, 4), (2, 4), (3, 6), (4, 8), (3, 6)]

TRAILS = ["Pine Ridge", "Fox Hollow", "Lantern Peak", "Mossy Creek", "Heron Lake", "Windy Saddle"]
DAYS = ["Saturday", "Sunday", "Saturday", "Saturday", "Sunday", "Friday evening"]
TIMES = ["6:30", "7:00", "7:30", "8:00", "9:00"]
ITEMS = ["boots", "rain jacket", "headlamp", "water bottle", "sunscreen", "trekking poles", "first aid kit", "map"]
FOODS = ["sandwiches", "trail mix", "bananas", "coffee", "tea", "dumplings", "oranges", "chocolate"]
EMOJIS = ["⛰️", "⛰️", "🥾", "🥾", "😂", "😂", "😂", "👍", "👍", "👍🏽", "☀️", "🌧️", "🙌", "😅", "❤️", "🔥", "🧗‍♀️", "😴"]

OPENERS = [
    "Who is in for {trail} on {day}?",
    "Weather for {day} looks good, thinking {trail}",
    "Anyone free for a short hike on {day}?",
    "Forecast says rain on {day}, should we move the hike?",
    "I found a new route near {trail}, about 12 km",
    "Reminder: we meet at {time} at the car park",
    "Can someone bring a spare {item}?",
    "My legs are still sore from {trail}",
    "Photos from {trail} are amazing",
    "What time are we starting on {day}?",
    "Is the {trail} trail open after the storm?",
    "I can drive on {day}, three seats free",
    "Should we do the long loop or the short one?",
    "Planning thread for {day}: route, cars, food",
]
REPLIES = [
    "I am in",
    "Count me in",
    "Sounds good",
    "Works for me",
    "Not sure yet, will confirm tonight",
    "Can we start at {time} instead?",
    "I will bring {food}",
    "I have a spare {item}",
    "Do not forget your {item}",
    "That climb was brutal last time",
    "The view from the top is worth it",
    "Checking the weather again tomorrow",
    "I need new boots before {day}",
    "Train or car?",
    "I can pick up two people on the way",
    "Let us keep it easy this week",
    "Great idea",
    "Too early for me",
    "Perfect",
    "Who has the map?",
    "My knee says short loop",
    "Long loop please",
    "Bringing {food} for everyone",
    "Same plan as last week then",
    "Agreed, {trail} it is",
    "Trail was muddy but fun",
    "Next time we go to {trail}",
    "See you all at {time}",
    "Running ten minutes late",
    "Almost there",
    "Home safe, thanks everyone",
    "Best hike so far",
    "haha yes",
    "ok",
    "Thanks!",
]
LINKS = [
    "Route is here: https://example.com/trails/{slug}",
    "Weather link https://example.org/forecast/{slug}",
    "Trail report says it is open: https://example.com/reports/{slug}",
    "Booked the hut, details at https://example.org/huts/{slug}",
]
PACKING_LISTS = [
    "Packing list for {day}:\n- {item}\n- {item2}\n\n2 litres of water each\n10/10 would recommend the {food}",
    "Plan for {day}:\nMeet: {time} at the car park\nRoute: {trail} - long loop\nFood: {food}",
    "Cars for {day}:\n1. Mira - three seats\n2. Bruno - two seats\nEveryone else takes the train",
]
MEDIA_TYPES = ["image", "image", "image", "video", "sticker", "GIF"]


@dataclass(frozen=True)
class Event:
    when: datetime
    sender: str | None  # None for system notices
    kind: str  # "text", "media", "deleted", "system" or "encryption"
    text: str = ""
    media: str = ""  # image, video, sticker or GIF
    edited: bool = False


class Dice:
    """Small helpers over random.random(), whose sequence is stable across Python versions."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def chance(self, probability: float) -> bool:
        return self._rng.random() < probability

    def between(self, low: int, high: int) -> int:
        return low + int(self._rng.random() * (high - low + 1))

    def pick(self, options):
        return options[int(self._rng.random() * len(options))]

    def weighted(self, options, weights):
        target = self._rng.random() * sum(weights)
        for option, weight in zip(options, weights):
            target -= weight
            if target < 0:
                return option
        return options[-1]


def _members_on(day: date) -> list[str]:
    members = ["Mira", "Bruno", "Chen", "Dalia"]
    if day >= TOMASZ_JOINS:
        members.append("Tomasz")
    if INES_JOINS <= day < INES_LEAVES:
        members.append("Ines")
    return members


def _fill(dice: Dice, template: str) -> str:
    trail = dice.pick(TRAILS)
    item = dice.pick(ITEMS)
    return template.format(
        trail=trail,
        slug=trail.lower().replace(" ", "-"),
        day=dice.pick(DAYS),
        time=dice.pick(TIMES),
        item=item,
        item2=dice.pick([i for i in ITEMS if i != item]),
        food=dice.pick(FOODS),
    )


def _with_emoji(dice: Dice, text: str) -> str:
    if dice.chance(0.3):
        text += " " + dice.pick(EMOJIS)
        if dice.chance(0.2):
            text += dice.pick(EMOJIS)
    return text


def _thread(dice: Dice, day: date) -> list[Event]:
    """One short conversation: an opener followed by a few replies."""
    members = _members_on(day)
    weights = [WEIGHTS[m] for m in members]
    hour = dice.weighted(list(range(24)), HOUR_WEIGHTS)
    when = datetime(day.year, day.month, day.day, hour, dice.between(0, 59), dice.between(0, 59))

    events = []
    previous = None
    for position in range(dice.between(2, 9)):
        sender = dice.weighted(members, weights)
        if sender == previous:
            sender = dice.weighted(members, weights)
        previous = sender

        roll = dice.between(1, 100)
        if position == 0:
            events.append(Event(when, sender, "text", _with_emoji(dice, _fill(dice, dice.pick(OPENERS)))))
        elif roll <= 8:
            events.append(Event(when, sender, "media", media=dice.pick(MEDIA_TYPES)))
        elif roll <= 12:
            events.append(Event(when, sender, "text", _fill(dice, dice.pick(LINKS))))
        elif roll <= 15:
            events.append(Event(when, sender, "text", _fill(dice, dice.pick(PACKING_LISTS))))
        elif roll <= 16:
            events.append(Event(when, sender, "deleted"))
        elif roll <= 20:
            events.append(Event(when, sender, "text", dice.pick(EMOJIS) * dice.between(1, 3)))
        else:
            text = _with_emoji(dice, _fill(dice, dice.pick(REPLIES)))
            events.append(Event(when, sender, "text", text, edited=dice.chance(0.02)))
        when += timedelta(seconds=dice.between(20, 240))
    return events


def build_events(seed: int = SEED) -> list[Event]:
    """Return the whole fictional conversation, oldest message first."""
    dice = Dice(seed)

    def at(day: date, hour: int, minute: int) -> datetime:
        return datetime(day.year, day.month, day.day, hour, minute)

    opening = at(START, 6, 0)
    events = [
        Event(opening, None, "encryption", ENCRYPTION_NOTICE),
        Event(opening, None, "system", f'Mira created group "{GROUP_OLD}"'),
        Event(opening, None, "system", "Mira added Bruno"),
        Event(opening, None, "system", "Mira added Chen"),
        Event(opening, None, "system", "Mira added Dalia"),
        Event(opening + timedelta(minutes=1), "Mira", "text", LABEL),
        Event(
            opening + timedelta(minutes=2),
            None,
            "system",
            f'Mira changed the subject from "{GROUP_OLD}" to "{GROUP}"',
        ),
        Event(at(TOMASZ_JOINS, 6, 0), None, "system", "Mira added Tomasz"),
        Event(at(INES_JOINS, 6, 0), None, "system", "Ines joined using this group's invite link"),
        Event(at(INES_LEAVES, 6, 0), None, "system", "Ines left"),
    ]

    for offset in range(WEEKS * 7):
        day = START + timedelta(days=offset)
        if dice.chance(0.08):
            continue  # a quiet day
        low, high = THREADS_PER_DAY[day.weekday()]
        for _ in range(dice.between(low, high)):
            events.extend(_thread(dice, day))

    # sorted() is stable, so events that share a timestamp keep their order.
    return sorted(events, key=lambda e: e.when)


def render_android(events: list[Event]) -> str:
    lines = []
    for e in events:
        stamp = e.when.strftime("%d/%m/%Y, %H:%M")
        if e.sender is None:
            lines.append(f"{stamp} - {e.text}")
            continue
        if e.kind == "media":
            body = "<Media omitted>"
        elif e.kind == "deleted":
            body = "This message was deleted"
        else:
            body = e.text + (" <This message was edited>" if e.edited else "")
        lines.append(f"{stamp} - {e.sender}: {body}")
    return "\n".join(lines) + "\n"


def _curly_quotes(text: str) -> str:
    """iPhone writes group names in curly quotes."""
    return text.replace(' "', " " + OPEN_QUOTE).replace('"', CLOSE_QUOTE)


def render_iphone(events: list[Event]) -> str:
    lines = []
    for e in events:
        hour = e.when.hour % 12 or 12
        half = "AM" if e.when.hour < 12 else "PM"
        stamp = f"[{e.when.month}/{e.when.day}/{e.when:%y}, {hour}:{e.when:%M:%S}{NNBSP}{half}]"
        if e.kind == "encryption":
            lines.append(f"{stamp} {GROUP}: {LRM}{e.text}")
        elif e.sender is None:
            lines.append(f"{stamp} {LRM}{_curly_quotes(e.text)}")
        elif e.kind == "media":
            lines.append(f"{stamp} {e.sender}: {LRM}{e.media} omitted")
        elif e.kind == "deleted":
            lines.append(f"{stamp} {e.sender}: {LRM}This message was deleted.")
        else:
            body = e.text + (f" {LRM}<This message was edited>" if e.edited else "")
            lines.append(f"{stamp} {e.sender}: {body}")
    return "\n".join(lines) + "\n"


def main() -> None:
    events = build_events()
    EXAMPLES.mkdir(exist_ok=True)
    for path, render in ((ANDROID_FILE, render_android), (IPHONE_FILE, render_iphone)):
        path.write_text(render(events), encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(EXAMPLES.parent)}")
    people = sorted({e.sender for e in events if e.sender})
    print(f"{len(events)} lines of chat from {len(people)} fictional people: {', '.join(people)}")


if __name__ == "__main__":
    main()
