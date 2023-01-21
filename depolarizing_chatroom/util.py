from typing import Any, Dict, List, Tuple, TypedDict

from .constants import MIN_COUNTED_MESSAGE_WORD_COUNT


class Message(TypedDict):
    body: str
    position: str
    rephrased: bool


# TODO: Fix these type hints
def calculate_turns(
    messages: List[Message], current_position: str
) -> Tuple[int, int, int, bool, List[List[Message]]]:
    turns = []
    # Note that this number, confusingly, is not the length of the yielded list.
    # TODO: Future me: why not?
    counted_turn_count = 0
    user_turn_count = 0
    partner_turn_count = 0
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
        if not turn_has_counted_message and (
            len(message["body"].split()) >= MIN_COUNTED_MESSAGE_WORD_COUNT
            # Also count a message as part of a turn if it was the result of a
            # rephrasing, regardless of whether it was the original message or a
            # rephrasing, because it means that the user recieved a rephrasing
            or message.get("rephrased", False)
        ):
            counted_turn_count += 1
            turn_has_counted_message = True
            if message_position == current_position:
                user_turn_count += 1
            else:
                partner_turn_count += 1
        turns[-1].append(message)
    return (
        counted_turn_count,
        user_turn_count,
        partner_turn_count,
        turn_has_counted_message,
        turns,
    )


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
