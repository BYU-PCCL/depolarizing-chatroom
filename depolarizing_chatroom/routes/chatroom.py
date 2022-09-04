import asyncio
import random
from datetime import datetime

from fastapi import Depends
from pydantic import BaseModel

from .. import (
    app,
    socket_manager,
    DataAccess,
    get_data_access,
    get_user_from_auth_code,
    suggest_rephrasings as sr,
)
from ..constants import (
    MIN_COUNTED_MESSAGE_WORD_COUNT,
    MIN_REPHRASING_TURNS,
    REPHRASE_EVERY_N_TURNS,
    SOCKET_NAMESPACE_CHATROOM,
)
from ..data import models
from ..data.models import UserPosition
from ..data.template import (
    HorribleConfusingListWrapperThatMakesTemplateAccessPatternWork,
)
from ..suggest_rephrasings import STRATEGY_LOGIT_BIASES, BASE_LOGIT_BIASES
from ..util import calculate_turns, last_n_turns


class InitialViewBody(BaseModel):
    view: str


@app.get("/chatroom")
def chatroom(
    user: models.User = Depends(get_user_from_auth_code),
    access: DataAccess = Depends(get_data_access),
):
    # If user is not in a chatroom, redirect to waiting room
    if not user.chatroom_id:
        return {"redirect": "waiting"}
    chatroom_id = user.chatroom_id
    # get all previously sent messages in the chatroom
    messages = (
        access.session.query(models.Message).filter_by(chatroom_id=chatroom_id).all()
    )
    prompt = (
        access.session.query(models.Chatroom).filter_by(id=chatroom_id).first().prompt
    )
    return {"prompt": prompt, "messages": messages, "id": chatroom_id}


@app.post("/initial-view")
async def initial_view(
    body: InitialViewBody,
    user: models.User = Depends(get_user_from_auth_code),
    access: DataAccess = Depends(get_data_access),
):
    user.view = body.view
    access.commit()


@socket_manager.on("connect", namespace=SOCKET_NAMESPACE_CHATROOM)
async def handle_connect(session_id, _environ, auth) -> None:
    from .. import get_data_access

    access = get_data_access()

    try:
        user_id = auth["token"]
    except KeyError:
        return

    user = access.session.query(models.User).filter_by(response_id=user_id).first()

    if not user:
        return

    await socket_manager.save_session(
        session_id, {"id": user_id}, namespace=SOCKET_NAMESPACE_CHATROOM
    )

    socket_manager.enter_room(
        session_id, user.chatroom_id, namespace=SOCKET_NAMESPACE_CHATROOM
    )
    # TODO: Handle pairing with other users—and notifying them
    # await socket_manager.emit(
    #     "new_message", body, room=f"chatroom-{body['id']}", callback=message_received
    # )

    messages = []
    for message in access.session.query(models.Message).filter_by(
        chatroom_id=user.chatroom_id
    ):
        messages.append(
            {
                "id": message.id,
                "user_id": message.user.id,
                "message": message.selected_body,
            }
        )

    await socket_manager.emit(
        f"messages",
        messages,
        to=session_id,
        namespace=SOCKET_NAMESPACE_CHATROOM,
    )


async def get_socket_session_user(access: DataAccess, session_id: str) -> models.User:
    user_id = (
        await socket_manager.get_session(
            session_id, namespace=SOCKET_NAMESPACE_CHATROOM
        )
    )["id"]
    user = access.session.query(models.User).filter_by(response_id=user_id).first()

    return user


async def redirect_to_waiting(session_id) -> None:
    await socket_manager.emit(
        "redirect",
        {"to": "waiting"},
        to=session_id,
        namespace=SOCKET_NAMESPACE_CHATROOM,
    )


@socket_manager.on("rephrasing_response", namespace=SOCKET_NAMESPACE_CHATROOM)
async def handle_rephrasing_response(session_id, body) -> None:
    from .. import get_data_access

    access = get_data_access()

    try:
        user = await get_socket_session_user(access, session_id)
    except KeyError:
        await redirect_to_waiting(session_id)
        return

    user_id = user.id

    chatroom_id = user.chatroom_id
    if not chatroom_id:
        await redirect_to_waiting(session_id)
        return

    message_id = body["message_id"]
    message_body = body["body"]
    message = access.session.query(models.Message).filter_by(id=message_id).first()

    if message.sender_id != user.id or message.chatroom_id != chatroom_id:
        return

    rephrasing_id = body.get("rephrasing_id")
    if rephrasing_id:
        rephrasing = (
            access.session.query(models.Rephrasing).filter_by(id=rephrasing_id).first()
        )

        if rephrasing.message_id != message.id:
            return

        if rephrasing.body != message_body:
            rephrasing.edited_body = message_body

        message.accepted_rephrasing_id = rephrasing.id
    else:
        # I'm pretty sure this is done implicitly
        message.accepted_rephrasing_id = None

        if message.body != message_body:
            message.edited_body = message_body

    # get user
    user = access.session.query(models.User).filter_by(id=user_id).first()

    # update message count
    # VIN HOWE: REMOVE THIS FOR NOW
    # user.message_count += 1  # increment user message count
    access.commit()
    body["count"] = user.message_count

    """
    Check if user has exceeded chat limit, if so redirect to survey
    TODO what should the limit be, especially for two people
    """
    # get chatroom, send message
    chatroom = access.session.query(models.Chatroom).filter_by(id=chatroom_id).first()

    # if user.message_count >= MESSAGE_LIMIT:
    #     # redirect each user
    #     for u in chatroom.users:
    #         u.status = "postsurvey"
    #     access.commit()
    #     body["redirect"] = "/"

    response = dict(
        user_id=user_id,
        message=message.selected_body,
    )

    await socket_manager.emit(
        f"new_message", response, to=chatroom_id, namespace=SOCKET_NAMESPACE_CHATROOM
    )


@socket_manager.on("typing", namespace=SOCKET_NAMESPACE_CHATROOM)
async def handle_typing(session_id):
    from .. import get_data_access

    access = get_data_access()

    try:
        user = await get_socket_session_user(access, session_id)
    except KeyError:
        await redirect_to_waiting(session_id)
        return

    chatroom = user.chatroom
    if not chatroom:
        await redirect_to_waiting(session_id)
        return

    room_ids = set(
        socket_manager._sio.manager.rooms[SOCKET_NAMESPACE_CHATROOM][chatroom.id].keys()
    )
    # Get other user's session ID
    other_session_id = next(iter(room_ids - {session_id}))

    await socket_manager.emit(
        "typing",
        to=other_session_id,
        namespace=SOCKET_NAMESPACE_CHATROOM,
    )


def generate_rephrasings():
    pass


@socket_manager.on("message", namespace=SOCKET_NAMESPACE_CHATROOM)
async def handle_message_sent(session_id, body):
    from .. import get_data_access
    from .. import get_templates

    access = get_data_access()
    templates = get_templates()

    try:
        user = await get_socket_session_user(access, session_id)
    except KeyError:
        await redirect_to_waiting(session_id)
        return

    chatroom_id = user.chatroom_id
    chatroom = (
        access.session.query(models.Chatroom).filter_by(id=user.chatroom_id).first()
    )
    if not chatroom:
        await redirect_to_waiting(session_id)
        return

    message = body["body"]

    chatroom_messages = (
        access.session.query(models.Message)
        .filter_by(chatroom_id=chatroom_id)
        .order_by(models.Message.send_time.asc())
        .all()
    )

    # Count messages, not including anything with fewer than 4 words (just counting by
    # spaces), a turn only happens if one user sends at least one message with at least
    # 4 words, and we need 3 turns, or three alternating chunks of at least one message
    # with at least 4 words. So we calculate turns and only send rephrasings if we have
    # turns % 3 == 0. Probably a little expensive, but it seems fine.
    # We'll rephrase the first message sent because the first two messages are input
    # before the chat starts.

    will_attempt_rephrasings = False
    user_position = "oppose" if user.position is UserPosition.OPPOSE else "support"
    turn_count, user_turn_count, last_turn_counted, turns = calculate_turns(
        [
            {
                "position": "oppose"
                if message.user.position is UserPosition.OPPOSE
                else "support",
                "body": message.selected_body,
            }
            for message in chatroom_messages
        ],
        user_position,
    )
    if user.receives_rephrasings:
        message_is_min_length = len(message.split()) >= MIN_COUNTED_MESSAGE_WORD_COUNT
        new_turn = chatroom_messages and user.id != chatroom_messages[-1].sender_id

        will_attempt_rephrasings = False

        if message_is_min_length and (new_turn or not last_turn_counted):
            user_turn_count += 1
            will_attempt_rephrasings = (
                turn_count >= MIN_REPHRASING_TURNS
                and user_turn_count % REPHRASE_EVERY_N_TURNS == 0
            )

    access.add_to_db(
        message := models.Message(
            chatroom_id=chatroom.id,
            sender_id=user.id,
            body=message,
            send_time=datetime.now(),
        )
    )
    access.commit()

    await socket_manager.emit(
        "rephrasings_status",
        dict(will_attempt=will_attempt_rephrasings),
        to=session_id,
        namespace=SOCKET_NAMESPACE_CHATROOM,
    )

    if not will_attempt_rephrasings:
        await socket_manager.emit(
            f"new_message",
            dict(
                user_id=user.id,
                message=message.body,
            ),
            to=chatroom_id,
            namespace=SOCKET_NAMESPACE_CHATROOM,
        )
        return

    # Give socket manager a chance to send the notification message
    await asyncio.sleep(0.2)

    last_turn_is_user = (
        user_turn_count > 0 and turns[-1][0]["position"] == user_position
    )

    # 10 doesn't mean anything, it's just a number high enough that I imagine we'd never
    # construct a template that uses that many turns.
    template_turns = last_n_turns(turns, 10)

    template_rephrasing_message = {
        "position": "oppose" if user.position is UserPosition.OPPOSE else "support",
        "body": message.selected_body,
    }

    if last_turn_is_user:
        template_turns[-1].append(template_rephrasing_message)
    else:
        template_turns.append([template_rephrasing_message])

    # print()
    # print("⭐️⭐️ Prompt ⭐️⭐️")
    # print()
    # print(sr.create_prompt(turns, sr.rephrasing_specs["validate"]))

    rephrasings = []
    for strategy, template in templates.items():
        prompt = template.render(
            HorribleConfusingListWrapperThatMakesTemplateAccessPatternWork(
                template_turns
            )
        )
        (response,), _ = sr.collect_rephrasings(
            sr.rephrasings_generator(
                prompt,
                logit_bias={
                    **(STRATEGY_LOGIT_BIASES.get(strategy, {})),
                    **BASE_LOGIT_BIASES,
                },
                n=1,
            )
        )
        rephrasings.append(models.Rephrasing(message_id=message.id, body=response))

    access.session.add_all(rephrasings)
    access.commit()

    # We want to present rephrasings in a random order
    random.shuffle(rephrasings)

    await socket_manager.emit(
        "rephrasings_response",
        dict(
            message_id=message.id,
            body=message.body,
            rephrasings=[{"id": r.id, "body": r.body} for r in rephrasings],
        ),
        to=session_id,
        namespace=SOCKET_NAMESPACE_CHATROOM,
    )


@socket_manager.on("clear", namespace=SOCKET_NAMESPACE_CHATROOM)
async def clear_chatroom(session_id):
    from .. import get_data_access

    access = get_data_access()

    try:
        user = await get_socket_session_user(access, session_id)
    except KeyError:
        socket_manager.emit(
            "redirect",
            {"to": "waiting"},
            to=session_id,
            namespace=SOCKET_NAMESPACE_CHATROOM,
        )
        return

    # get chatroom
    chatroom_id = user.chatroom_id

    chatroom = access.session.query(models.Chatroom).filter_by(id=chatroom_id).first()
    if not chatroom:
        await redirect_to_waiting(session_id)
        return
    for message in chatroom.messages:
        access.session.delete(message)

    access.commit()

    await socket_manager.emit(
        f"clear", chatroom_id, namespace=SOCKET_NAMESPACE_CHATROOM
    )
