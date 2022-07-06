from datetime import datetime

import numpy as np

from .. import (
    socket_manager,
    DataAccess,
)
from ..constants import SOCKET_NAMESPACE_WAITING_ROOM
from ..data import models


@socket_manager.on("connect", namespace=SOCKET_NAMESPACE_WAITING_ROOM)
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

    if not user.view:
        await socket_manager.emit(
            "redirect",
            {"to": "view"},
            to=session_id,
            namespace=SOCKET_NAMESPACE_WAITING_ROOM,
        )
        return

    if user.chatroom:
        await socket_manager.emit(
            "redirect",
            {"to": "chatroom"},
            to=session_id,
            namespace=SOCKET_NAMESPACE_WAITING_ROOM,
        )
        return

    await socket_manager.save_session(
        session_id, {"id": user_id}, namespace=SOCKET_NAMESPACE_WAITING_ROOM
    )

    access.session.commit()

    # Add user to waiting room
    user.started_waiting = datetime.now()
    user.finished_waiting = None
    user.waiting_session_id = session_id

    access.session.commit()

    # Get all available matches by treatment code
    matching_user = (
        access.session.query(models.User)
        .populate_existing()
        .filter(
            models.User.started_waiting.isnot(None),
            models.User.treatment == user.match_with,
        )
    ).first()

    if not matching_user:
        # No match found, wait for another user to join
        return

    # Create a chatroom and put users together
    access.session.add(
        chatroom := models.Chatroom(prompt="Gun Control in America: More or Less?")
    )
    user.chatroom = chatroom
    matching_user.chatroom = chatroom
    access.session.commit()

    user_view_message = models.Message(
        chatroom_id=chatroom.id,
        sender_id=user.id,
        body=user.view,
        send_time=datetime.now(),
    )
    matching_user_view_message = models.Message(
        chatroom_id=chatroom.id,
        sender_id=matching_user.id,
        body=matching_user.view,
        send_time=datetime.now(),
    )

    # Add initial views to chatroom in random order
    if np.random.random() < 0.5:
        access.session.add(user_view_message)
        access.session.add(matching_user_view_message)
    else:
        access.session.add(matching_user_view_message)
        access.session.add(user_view_message)

    finished_waiting = datetime.now()
    matching_user.finished_waiting = finished_waiting
    user.finished_waiting = finished_waiting

    user_waiting_session_id = user.waiting_session_id
    matching_user_waiting_session_id = matching_user.waiting_session_id

    matching_user.waiting_session_id = None
    user.waiting_session_id = None
    access.session.commit()

    # Send messages to both users
    for session_id in (user_waiting_session_id, matching_user_waiting_session_id):
        await socket_manager.emit(
            "redirect",
            {"to": "chatroom"},
            to=session_id,
            namespace=SOCKET_NAMESPACE_WAITING_ROOM,
        )


async def get_socket_session_user(access: DataAccess, session_id: str) -> models.User:
    # Duplicated from chatroom
    user_id = (
        await socket_manager.get_session(
            session_id, namespace=SOCKET_NAMESPACE_WAITING_ROOM
        )
    )["id"]
    user = access.session.query(models.User).filter_by(response_id=user_id).first()

    return user


@socket_manager.on("disconnect", namespace=SOCKET_NAMESPACE_WAITING_ROOM)
async def handle_disconnect(session_id) -> None:
    from .. import get_data_access

    access = get_data_access()

    user = await get_socket_session_user(access, session_id)
    if not user:
        return

    # Remove user from waiting room pool
    user.started_waiting = None
    user.finished_waiting = None
    user.waiting_session_id = None
    access.session.commit()
