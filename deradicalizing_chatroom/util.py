import random
from datetime import datetime
from hashlib import sha256
from secrets import choice
from string import ascii_letters, digits
from typing import List, Tuple

from deradicalizing_chatroom.constants import MIN_COUNTED_MESSAGE_WORD_COUNT
from deradicalizing_chatroom.data import models


def random_color():
    return "#" + str(hex(random.randint(0, 16777215)))[2:]


def sec(n):
    alphabet = ascii_letters + digits
    return "".join(choice(alphabet) for _ in range(n))


def hash_pw(p, s):
    return sha256(bytes(p + s, "utf-8")).hexdigest()


def calculate_turns(
    messages: List[models.Message], current_user_id: int
) -> Tuple[int, int, bool, List[List[models.Message]]]:
    turns = []
    # Note that this number, confusingly, is not the length of the yielded list.
    counted_turn_count = 0
    user_turn_count = 0
    last_message_sender_id = None
    turn_has_counted_message = False
    for message in messages:
        # Only count a turn if the message is at least 4 words long AND it was sent by a
        # different user than the message before it.
        if message.sender_id != last_message_sender_id:
            turns.append([])
            turn_has_counted_message = False
            last_message_sender_id = message.sender_id
        if (
            not turn_has_counted_message
            and len(message.selected_body.split()) >= MIN_COUNTED_MESSAGE_WORD_COUNT
        ):
            counted_turn_count += 1
            turn_has_counted_message = True
            if message.sender_id == current_user_id:
                user_turn_count += 1
        turns[-1].append(message)
    return counted_turn_count, user_turn_count, turn_has_counted_message, turns


def last_n_turns(turns: List[List[models.Message]], n: int) -> List[models.Message]:
    n_turns = []
    counted_turn_count = 0
    for turn in turns:
        if counted_turn_count >= n:
            break
        if any(
            len(message.selected_body.split()) >= MIN_COUNTED_MESSAGE_WORD_COUNT
            for message in turn
        ):
            counted_turn_count += 1
        n_turns.extend(turn)
    return n_turns


def format_dt(val: datetime) -> str:
    return val.strftime("%H:%M | %b %d, '%y")
