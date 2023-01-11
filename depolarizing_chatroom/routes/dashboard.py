from pydantic import BaseModel

from ..data.crud import access
from ..data.models import UserPosition
from ..server import app


class StatsByPosition(BaseModel):
    supporters: int
    opponents: int


class Stats(BaseModel):
    totalOnline: int
    unmatched: StatsByPosition
    prechat: StatsByPosition
    inChatroom: StatsByPosition


@app.get("/stats")
async def stats() -> Stats:
    # TODO: Consider a gather call here just because we're awaiting so many things right
    #  after each other.
    unmatched_supporter_count = len(
        await access.users_in_waiting_room(position=UserPosition.SUPPORT, matched=False)
    )
    unmatched_opponent_count = len(
        await access.users_in_waiting_room(position=UserPosition.OPPOSE, matched=False)
    )
    pre_chat_supporter_count = len(
        await access.users_in_waiting_room(position=UserPosition.SUPPORT, matched=True)
    )
    pre_chat_opponent_count = len(
        await access.users_in_waiting_room(position=UserPosition.OPPOSE, matched=True)
    )
    in_chatroom_supporter_count = len(
        await access.users_in_chatroom(position=UserPosition.SUPPORT)
    )
    in_chatroom_opponent_count = len(
        await access.users_in_chatroom(position=UserPosition.OPPOSE)
    )
    total_online = (
        unmatched_supporter_count
        + unmatched_opponent_count
        + pre_chat_supporter_count
        + pre_chat_opponent_count
        + in_chatroom_supporter_count
        + in_chatroom_opponent_count
    )

    return Stats(
        totalOnline=total_online,
        unmatched=StatsByPosition(
            supporters=unmatched_supporter_count,
            opponents=unmatched_opponent_count,
        ),
        prechat=StatsByPosition(
            supporters=pre_chat_supporter_count,
            opponents=pre_chat_opponent_count,
        ),
        inChatroom=StatsByPosition(
            supporters=in_chatroom_supporter_count,
            opponents=in_chatroom_opponent_count,
        ),
    )
