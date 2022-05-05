import asyncio
from datetime import datetime

from fastapi import Depends, HTTPException
from fastapi.requests import Request
from fastapi.responses import HTMLResponse

import suggest_rephrasings as sr
from .. import (
    app,
    very_insecure_session_auth_we_know_the_risks,
    templates,
    socket_manager,
    DataAccess,
    get_data_access,
)
from ..constants import MESSAGE_LIMIT
from ..data import models
from ..util import message_received, format_dt


@app.get("/chatroom/{chatroom_id}")
def chatroom(
    chatroom_id: int,
    request: Request,
    _: None = Depends(very_insecure_session_auth_we_know_the_risks),
    access: DataAccess = Depends(get_data_access),
) -> HTMLResponse:
    # get user information from db
    user = (
        access.session.query(models.User)
        .filter_by(email=request.session["user"]["email"])
        .first()
    )
    if user.chatroom_id != chatroom_id:
        raise HTTPException(status_code=401, detail="Invalid chatroom")
    # get all previously sent messages in the chatroom
    messages = (
        access.session.query(models.Message).filter_by(chatroom_id=chatroom_id).all()
    )
    prompt = (
        access.session.query(models.Chatroom).filter_by(id=chatroom_id).first().prompt
    )
    return templates.TemplateResponse(
        "chatroom_bs.html",
        dict(
            request=request,
            username=user.username,
            affiliation=user.affiliation,
            color=user.color,
            user_id=user.id,
            chatroom_id=chatroom_id,
            messages=messages,
            prompt=prompt,
            message_count=user.message_count,
            message_limit=MESSAGE_LIMIT,
        ),
    )


@socket_manager.on("join_chatroom")
async def handle_join(session_id, body) -> None:
    await socket_manager.emit("joined_chatroom", body, callback=message_received)


@socket_manager.on("new_message")
async def handle_new_message(session_id, body) -> None:
    from .. import access

    user_id = body["user_id"]
    chatroom_id = body["chatroom_id"]

    message_id = body["message_id"]
    message = access.session.query(models.Message).filter_by(id=message_id).first()

    # This is horrible and beyond insecure.
    if message.sender_id != user_id or message.chatroom_id != chatroom_id:
        return

    rephrasing_id = body.get("rephrasing_id")
    rephrasing = None
    if rephrasing_id:
        rephrasing = (
            access.session.query(models.Rephrasing).filter_by(id=rephrasing_id).first()
        )

        if rephrasing.message_id != message.id:
            return

        message.accepted_rephrasing_id = rephrasing.id
    else:
        # I'm pretty sure this is done implicitly
        message.accepted_rephrasing_id = None

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

    if user.message_count >= MESSAGE_LIMIT:
        # redirect each user
        for u in chatroom.users:
            u.status = "postsurvey"
        access.commit()
        body["redirect"] = "/"

    response = dict(
        user_id=user_id,
        chatroom_id=chatroom_id,
        is_rephrasing=bool(rephrasing),
        message=rephrasing and rephrasing.body or message.body,
    )

    await socket_manager.emit(
        f"new_message_{body['chatroom_id']}", response, callback=message_received
    )


@socket_manager.on("post")
async def handle_message_sent(session_id, body):
    print("message sent")
    from .. import access

    # store message in database

    message = body["body"]
    # get chatroom
    chatroom = (
        access.session.query(models.Chatroom).filter_by(id=body["chatroom_id"]).first()
    )

    # get user
    user = access.session.query(models.User).filter_by(id=body["user_id"]).first()

    # TODO(vinhowe): figure out how to get past n turns

    last_n_messages = (
        access.session.query(models.Message)
        .filter_by(chatroom_id=body["chatroom_id"])
        .order_by(models.Message.send_time.desc())
        .limit(3)
        .all()
    )

    print("Message")

    will_attempt_rephrasings = len(last_n_messages) >= 2

    await socket_manager.emit(
        f'rephrasings_status_{body["chatroom_id"]}_{body["user_id"]}',
        dict(will_attempt=will_attempt_rephrasings),
        callback=message_received,
    )

    if will_attempt_rephrasings:
        # Give socket manager a chance to send the notification message
        await asyncio.sleep(0.2)
        turns = [
            {
                "party": message.user.affiliation,
                "message": (rephrasing := message.accepted_rephrasing)
                and rephrasing.body
                or message.body,
            }
            for message in reversed(last_n_messages)
        ]
        turns.append({"party": user.affiliation, "message": message})
        print(sr.create_prompt(turns, sr.rephrasing_specs["validate"]))
        gpt_responses, _ = sr.collect_rephrasings(
            sr.create_rephrasing_for_turns(turns, sr.rephrasing_specs["validate"], n=3)
        )
    else:
        gpt_responses = []

    body["responses"] = gpt_responses

    access.add_to_db(
        message := models.Message(
            chatroom_id=chatroom.id,
            sender_id=user.id,
            body=message,
            send_time=datetime.now(),
        )
    )

    # Add rephrasings to db
    rephrasings = []
    for response in gpt_responses:
        rephrasing = models.Rephrasing(message_id=message.id, body=response)
        rephrasings.append(rephrasing)
        access.session.add(rephrasing)
    access.commit()

    body["time"] = format_dt(datetime.now())

    response = dict(
        message_id=message.id,
        body=message.body,
        rephrasings={r.id: r.body for r in rephrasings},
    )

    # send response to that chatroom
    await socket_manager.emit(
        f'response_{body["chatroom_id"]}_{body["user_id"]}',
        response,
        callback=message_received,
    )


@socket_manager.on("clear_chatroom")
async def clear_chatroom(session_id, body):
    from .. import access

    chatroom = (
        access.session.query(models.Chatroom).filter_by(id=body["chatroom_id"]).first()
    )
    for message in chatroom.messages:
        access.session.delete(message)

    access.commit()

    await socket_manager.emit(
        f'clear_chatroom_{body["chatroom_id"]}',
        callback=message_received,
    )
