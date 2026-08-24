EXPRESSIONS = {
    "neutral": {
        "status": "idle",
    },

    "happy": {
        "status": "speaking",
    },

    "sad": {
        "status": "speaking",
    },

    "angry": {
        "status": "speaking",
    },

    "surprised": {
        "status": "speaking",
    },

    "thinking": {
        "status": "thinking",
    },

    "listening": {
        "status": "listening",
    },
}


def get_expression(name: str):
    return EXPRESSIONS.get(
        name,
        EXPRESSIONS["neutral"],
    )