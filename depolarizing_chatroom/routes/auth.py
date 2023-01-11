from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from ..data import models
from ..data.crud import access
from ..data.models import UserPosition
from ..logger import logger, format_parameterized_log_message
from ..server import app, get_user_from_auth_code


class LoginBody(BaseModel):
    token: str


class SignupBody(BaseModel):
    respondentId: str
    position: UserPosition


class TestSignupBody(BaseModel):
    username: str
    pairWith: Optional[str]
    position: str
    applyTreatment: bool


class UserUpdateBody(BaseModel):
    leaveReason: Optional[str]


@app.get("/user")
async def user(user: models.User = Depends(get_user_from_auth_code)) -> dict:
    return {
        **user.__dict__,
        "post_survey_url": user.post_chat_url,
        "no_chat_url": user.no_chat_url,
    }


@app.put("/user")
async def user(
    body: UserUpdateBody, user: models.User = Depends(get_user_from_auth_code)
) -> dict:
    async with access.commit_after():
        if body.leaveReason:
            user.leave_reason = body.leaveReason
        access.save_event(user.id, "left_early", data=body.leaveReason)
    return {"status": "ok"}


@app.post("/login")
async def post_login(body: LoginBody) -> dict:
    async with access.commit_after():
        if not await access.process_login(body.token):
            raise HTTPException(status_code=401, detail="Invalid sign in.")

    return {"status": "ok"}


@app.post("/signup")
async def post_signup(body: SignupBody) -> dict:
    async with access.commit_after():
        user = await access.process_signup(body.respondentId, body.position)
    if user:
        # We have to do this after processing the signup because the user id is only
        # generated after the user is added to the database.
        async with access.commit_after():
            access.save_event(user.id, "signup")
    else:
        logger.warning(
            format_parameterized_log_message(
                "Tried to create new user with existing respondent ID",
                respondent_id=body.respondentId,
            )
        )
        # TODO: Consider handling this with some kind of error
        return {"status": "ok"}

    logger.info(
        format_parameterized_log_message(
            "Created new user",
            user_id=user.id,
            respondent_id=body.respondentId,
            position=body.position.value,
        )
    )
    return {"status": "ok"}
