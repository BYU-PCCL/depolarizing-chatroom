# NO NEED FOR WAITING ROOM IF PEOPLE NOT CHATTING W EACH OTHER
# unique waiting room for each user
from datetime import datetime

from fastapi import Depends, HTTPException
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc

from .chatroom import message_received
from .. import (
    app,
    socket_manager,
    very_insecure_session_auth_we_know_the_risks,
    templates,
    get_data_access,
    DataAccess,
)
from ..constants import THRESHOLD
from ..data import models


@app.get("/waiting_room/{user_id}")
def waiting_room(
    user_id,
    request: Request,
    access: DataAccess = Depends(get_data_access),
    _: None = Depends(very_insecure_session_auth_we_know_the_risks),
) -> HTMLResponse:
    # get user information from db
    u = (
        access.session.query(models.User)
        .filter_by(email=request.session["user"]["email"])
        .first()
    )

    # if cookie doesn't match user, we got a problem
    if u.id != int(user_id):
        raise HTTPException(status_code=401, detail="Invalid chatroom")

    # get number of people in that
    nq = (
        access.session.query(models.User)
        .filter(models.User.code_id == u.code.id, models.User.waiting is not None)
        .count()
    )

    return templates.TemplateResponse(
        "waiting_room.html",
        dict(request=request, user_id=user_id, threshold=THRESHOLD, num_queue=nq),
    )


@socket_manager.on("join_waiting_room")
async def handle_waiting_room(session_id, json):
    from .. import access

    # get current user
    user_id = json["user_id"]
    u = access.session.query(models.User).filter_by(id=int(user_id)).first()

    # add user to queue if not already in a chatroom
    u.waiting = datetime.now()
    access.commit()

    json["num_queue"] = (
        access.session.query(models.User)
        .filter(models.User.code_id == u.code.id, models.User.waiting is not None)
        .count()
    )

    # update limit
    await socket_manager.emit("joined_waiting_room", json, callback=message_received)

    # everytime someone joins, check and see if should redistribute people to chatroom
    print("checking")
    c = access.session.query(models.Code).filter_by(code=u.code.code).first()
    waiters = (
        access.session.query(models.User)
        .filter(models.User.code_id == c.id, models.User.waiting is not None)
        .order_by(desc(models.User.waiting))
        .all()
    )

    if len(waiters) >= THRESHOLD:
        print("people waiting:")
        print(waiters)
        us = waiters[:THRESHOLD]
        print(us)
        # create chatroom
        chatroom = models.Chatroom(code_id=c.id, prompt="Gun control: more or less?")
        access.add_to_db(chatroom)
        # redirect each user
        for u in us:
            # add relationships
            chatroom.users.append(u)
            u.chatroom_id = chatroom.id
            u.waiting = None
            u.status = "chatroom"

            print(f"Redirecting {u.id} to /chatroom/{chatroom.id}")
            await socket_manager.emit(
                f"waiting_room_redirect_{u.id}",
                {"redirect": f"/chatroom/{chatroom.id}"},
            )
        access.commit()
