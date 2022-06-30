from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.requests import Request
from pydantic import BaseModel

from .. import app, DataAccess, get_data_access, get_user_from_auth_code
from ..data import models
from ..data.models import UserPosition


class SignupBody(BaseModel):
    username: str
    pairWith: Optional[str]
    position: str
    applyTreatment: bool


class LoginBody(BaseModel):
    token: str


@app.get("/user")
def user(user: models.User = Depends(get_user_from_auth_code)) -> dict:
    return user


@app.post("/login")
def post_login(
    request: Request,
    body: LoginBody,
    access: DataAccess = Depends(get_data_access),
) -> dict:
    # TODO: if change login logic (e.g. password) will need to change if logging in,
    #  check if email is real

    if not (user := access.process_login(body.token)):
        raise HTTPException(status_code=401, detail="Invalid sign in.")

    request.session["user"] = {"response_id": body.token}

    return {"status": "ok"}


@app.post("/test-signup")
def post_test_signup(
    body: SignupBody,
    access: DataAccess = Depends(get_data_access),
) -> dict:
    position = (
        UserPosition.OPPOSE
        if body.position.lower() == "oppose"
        else UserPosition.SUPPORT
    )

    if not (
        signup_user := access.process_signup(
            body.username, position, body.applyTreatment
        )
    ):
        raise HTTPException(
            status_code=400, detail="Test signup already performed. Try signing in."
        )

    # Pair with an existing user
    if body.pairWith:
        pair_with_user = (
            access.session.query(models.User)
            .filter_by(response_id=body.pairWith)
            .first()
        )
        if pair_with_user:
            chatroom = access.add_chatroom("Gun Control in America: More or Less?")
            pair_with_user.chatroom_id = chatroom.id
            signup_user.chatroom_id = chatroom.id

    return {"status": "ok"}
