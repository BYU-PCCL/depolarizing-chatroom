import random
from datetime import datetime
from hashlib import sha256
from secrets import choice
from string import ascii_letters, digits
from typing import List, Tuple, Dict, Any, Optional, Callable

from . import DataAccess
from .constants import MIN_COUNTED_MESSAGE_WORD_COUNT
from .data import models


def random_color():
    return "#" + str(hex(random.randint(0, 16777215)))[2:]


def sec(n):
    alphabet = ascii_letters + digits
    return "".join(choice(alphabet) for _ in range(n))


def hash_pw(p, s):
    return sha256(bytes(p + s, "utf-8")).hexdigest()


def calculate_turns(
    messages: List[Dict[str, Any]], current_position: str
) -> Tuple[int, int, bool, List[List[models.Message]]]:
    turns = []
    # Note that this number, confusingly, is not the length of the yielded list.
    counted_turn_count = 0
    user_turn_count = 0
    last_message_position = None
    turn_has_counted_message = False
    for message in messages:
        # Only count a turn if the message is at least 4 words long AND it was sent by a
        # different user than the message before it.
        message_position = message["position"]
        if message_position != last_message_position:
            turns.append([])
            turn_has_counted_message = False
            last_message_position = message_position
        if (
            not turn_has_counted_message
            and len(message["body"].split()) >= MIN_COUNTED_MESSAGE_WORD_COUNT
        ):
            counted_turn_count += 1
            turn_has_counted_message = True
            if message_position == current_position:
                user_turn_count += 1
        turns[-1].append(message)
    return counted_turn_count, user_turn_count, turn_has_counted_message, turns


def last_n_turns(
    turns: List[List[Dict[str, Any]]], n: int
) -> List[List[Dict[str, Any]]]:
    n_turns = []
    counted_turn_count = 0
    for turn in turns[::-1]:
        if counted_turn_count >= n:
            break
        if any(
            len(message["body"].split()) >= MIN_COUNTED_MESSAGE_WORD_COUNT
            for message in turn
        ):
            counted_turn_count += 1
        n_turns.append(turn)
    return n_turns[::-1]


def check_socket_auth(auth, access) -> Optional[models.User]:
    try:
        user_id = auth["token"]
    except KeyError:
        return

    return access.session.query(models.User).filter_by(response_id=user_id).first()


def format_dt(val: datetime) -> str:
    return val.strftime("%H:%M | %b %d, '%y")


async def get_socket_session_user(
    access: DataAccess, session_id: str, get_session_fn: Callable, namespace: str
) -> Optional[models.User]:
    # Duplicated from chatroom
    try:
        user_id = (await get_session_fn(session_id, namespace=namespace))["id"]
    except KeyError:
        return

    user = access.session.query(models.User).filter_by(response_id=user_id).first()

    return user
