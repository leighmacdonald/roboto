from random import randint

_eight_ball_opts = [
    "It is certain",
    "Outlook good",
    "You may rely on it",
    "Ask again later",
    "Concentrate and ask again",
    "Reply hazy, try again",
    "My reply is no",
    "My sources say no"
]


def eight_ball() -> str:
    return _eight_ball_opts[randint(1, len(_eight_ball_opts))-1]
