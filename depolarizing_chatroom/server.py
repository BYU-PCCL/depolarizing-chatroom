import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from os import path
from typing import Dict

import socketio
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader
from fastapi_async_sqlalchemy import SQLAlchemyMiddleware, db
from fastapi_socketio import SocketManager
from starlette.middleware.sessions import SessionMiddleware

from .constants import SOCKET_NAMESPACE_WAITING_ROOM, WAITING_ROOM_TIMEOUT
from .data import models
from .data.crud import access

# from .data.database import SessionLocal, engine
from .data.template import TemplateManager, load_templates_from_directory
from .exceptions import AuthException
from .logger import format_parameterized_log_message, logger
from .socketio import RouteIgnoringMiddlewareWrapper, get_all_socketio_sessions

load_dotenv(path.join(path.dirname(__file__), ".env"))


app = FastAPI()

app.add_middleware(
    SessionMiddleware, secret_key=os.getenv("SECRET_KEY") or "default-secret"
)

SQLALCHEMY_DATABASE_URL = os.getenv("DB_URI") or "sqlite:///"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_manager = SocketManager(
    app=app, cors_allowed_origins=[], client_manager=socketio.AsyncRedisManager()
)

templates = load_templates_from_directory(os.getenv("TEMPLATES_DIR"))
executor = None


_API_KEY_NAME = "X-AUTH-CODE"
_api_key_header = APIKeyHeader(name=_API_KEY_NAME, auto_error=False)


async def waiting_room_timeout_loop() -> None:
    # noinspection PyProtectedMember
    sio = socket_manager._sio
    while True:
        async with db():
            try:
                socketio_sessions = await get_all_socketio_sessions(
                    sio, SOCKET_NAMESPACE_WAITING_ROOM
                )
                # Get ids
                ids = [s["id"] for s in socketio_sessions.values() if "id" in s]
                # Get users in waiting room
                users = await access.users_in_waiting_room(
                    filter_ids=ids, matched=False
                )
                for user in users:
                    # Redirect to no-chat post-chat survey if user is:
                    try:
                        if (
                            # - in a waiting room
                            user.waiting_session_id
                            # - unmatched
                            and user.chatroom_id is None
                            # - for more than WAITING_ROOM_TIMEOUT minutes
                            and user.started_waiting_time
                            and user.started_waiting_time
                            + timedelta(seconds=WAITING_ROOM_TIMEOUT)
                            < datetime.now()
                        ):
                            logger.warning(
                                format_parameterized_log_message(
                                    "User timed out in waiting room, redirecting to "
                                    "post-chat survey",
                                    user_id=user.id,
                                )
                            )
                            await sio.emit(
                                "redirect",
                                {"url": user.no_chat_url},
                                to=user.waiting_session_id,
                                namespace=SOCKET_NAMESPACE_WAITING_ROOM,
                            )
                            async with access.commit_after():
                                access.save_event(user.id, "redirect_no_chat")
                    except Exception:
                        logger.exception(
                            format_parameterized_log_message(
                                "Error while checking user in waiting room timeout",
                                user_id=user.id if hasattr(user, "id") else None,
                            )
                        )
                await asyncio.sleep(1)
            except Exception:
                # We can't have this loop fail
                logger.exception("Error in waiting room timeout loop")


@app.on_event("startup")
async def startup_event() -> None:
    # TODO: This should be moved to a contextvar
    global executor
    app.add_middleware(
        RouteIgnoringMiddlewareWrapper,
        wrapped_middleware_class=SQLAlchemyMiddleware,
        ignore_routes=["/ws/"],
        db_url=SQLALCHEMY_DATABASE_URL,
        # Echo
        # engine_args={"echo": True},
        # By default we get 100 connections from Postgres, so keep the max overflow low
        engine_args={"max_overflow": 4},
        session_args={"autoflush": False, "autocommit": False},
    )
    executor = ThreadPoolExecutor()
    asyncio.get_running_loop().create_task(waiting_room_timeout_loop())


def get_templates() -> Dict[str, TemplateManager]:
    return templates


def very_insecure_session_auth_we_know_the_risks(request: Request):
    if not request.session.get("user"):
        raise AuthException()


async def get_user_from_auth_code(
    header_key: str = Depends(_api_key_header),
) -> models.User:
    """
    Based on the example at
    https://fastapi.tiangolo.com/advanced/security/http-basic-auth/#check-the-username
    :raises HTTPException: if credentials are incorrect:
    """

    if header_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    async with access.commit_after():
        user = await access.user_by_response_id(header_key)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    return user


@app.exception_handler(AuthException)
async def auth_exception_handler(*_) -> RedirectResponse:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: Add a parameter to specify the redirect return URL
    return RedirectResponse("/login")


# We import these here to avoid circular imports
# noinspection PyUnresolvedReferences
from . import routes
