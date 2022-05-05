import random
from datetime import datetime
from hashlib import sha256
from secrets import choice
from string import ascii_letters, digits


def random_color():
    return "#" + str(hex(random.randint(0, 16777215)))[2:]


def sec(n):
    alphabet = ascii_letters + digits
    return "".join(choice(alphabet) for _ in range(n))


def hash_pw(p, s):
    return sha256(bytes(p + s, "utf-8")).hexdigest()


def message_received():
    print("message was received!!!")


def format_dt(val: datetime) -> str:
    return val.strftime("%H:%M | %b %d, '%y")
