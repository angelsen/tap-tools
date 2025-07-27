"""Session name generation utilities.

PUBLIC API:
  - generate_session_name: Generate Docker-style session names
"""

import random


def generate_session_name() -> str:
    """Generate a Docker-style session name (adjective-animal)."""
    adjectives = [
        "awesome",
        "bold",
        "brave",
        "busy",
        "clever",
        "cool",
        "eager",
        "epic",
        "fast",
        "focused",
        "friendly",
        "happy",
        "jolly",
        "kind",
        "loving",
        "lucid",
        "magical",
        "modest",
        "nice",
        "peaceful",
        "practical",
        "quirky",
        "relaxed",
        "sharp",
        "silly",
        "sleepy",
        "stoic",
        "sweet",
        "tender",
        "trusting",
        "zen",
    ]

    animals = [
        "ant",
        "bat",
        "bear",
        "bee",
        "bird",
        "cat",
        "crow",
        "deer",
        "dog",
        "dove",
        "duck",
        "eagle",
        "eel",
        "elk",
        "fox",
        "frog",
        "goat",
        "hawk",
        "heron",
        "horse",
        "koala",
        "lamb",
        "lion",
        "lynx",
        "moose",
        "mouse",
        "otter",
        "owl",
        "panda",
        "pig",
        "puma",
        "raven",
        "seal",
        "shark",
        "sheep",
        "snake",
        "swan",
        "tiger",
        "toad",
        "trout",
        "turtle",
        "viper",
        "whale",
        "wolf",
        "wombat",
        "yak",
        "zebra",
    ]

    adjective = random.choice(adjectives)
    animal = random.choice(animals)

    return f"{adjective}-{animal}"
