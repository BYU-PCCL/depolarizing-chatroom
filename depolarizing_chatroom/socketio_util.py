from typing import Any, Callable, Dict, List, Optional, Type

# TODO: Rename this file to socketio_util
import socketio_util
from fastapi_async_sqlalchemy import db
from socketio_util import AsyncNamespace
from starlette.middleware.base import BaseHTTPMiddleware

from .data import models
from .data.crud import access
from .logger import format_parameterized_log_message, logger


class RouteIgnoringMiddlewareWrapper(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        wrapped_middleware_class: Type[BaseHTTPMiddleware],
        *,
        ignore_routes: List[str],
        **kwargs,
    ):
        super().__init__(app)
        self._middleware = wrapped_middleware_class(app, **kwargs)
        self._ignore_routes = ignore_routes

    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(route) for route in self._ignore_routes):
            return await call_next(request)
        return await self._middleware.dispatch(request, call_next)


async def check_socket_auth(auth: Dict[Any, str]) -> Optional[models.User]:
    try:
        response_id = auth["token"]
    except KeyError:
        return

    return await access.user_by_response_id(response_id)


async def get_socket_session_user(session: Dict[str, Any]) -> Optional[models.User]:
    try:
        response_id = session["id"]
    except KeyError:
        return

    return await access.user(response_id)


async def get_all_socketio_sessions(
    server: socketio.AsyncServer, namespace: str
) -> Dict[str, Dict[str, Any]]:
    try:
        return {
            sid: (await server.eio.get_session(sid))[namespace]
            for sid in server.manager.rooms[namespace][None].values()
        }
    except KeyError:
        return {}


class SocketSession:
    def __init__(
        self,
        session_id: str,
        auth: Dict[str, Any],
        user: models.User,
        sio: socketio.AsyncNamespace,
    ):
        self._session_id = session_id
        self._auth = auth
        self._user = user
        self._sio = sio


class SessionSocketAsyncNamespace(AsyncNamespace):
    def __init__(self, session_class: Type[SocketSession], namespace: str):
        super().__init__(namespace)
        self._session_class = session_class

    def __getattr__(self, name, default=None) -> Callable:
        if not name.startswith("on_") or not hasattr(self._session_class, name):
            return getattr(super(), name, default)

        return self._make_handler(name)

    def _make_handler(self, name) -> Callable:
        async def handler(session_id, *args, **kwargs) -> None:
            async with db():
                # TODO: Unclear that we need this?
                session = await self.get_session(session_id)
                if not session:
                    logger.warning(
                        format_parameterized_log_message(
                            "Received message from unknown session",
                            session_id=session_id,
                        )
                    )
                    return
                if (response_id := session.get("id")) is None:
                    logger.warning(
                        format_parameterized_log_message(
                            "Received message from session without user response id",
                            session_id=session_id,
                        )
                    )
                    return
                if (user := await access.user(session["id"])) is None:
                    logger.warning(
                        format_parameterized_log_message(
                            "Received message from session with an invalid user id",
                            session_id=session_id,
                            # It could be a security issue to print things like this,
                            # but we'd have bigger problems if someone really wanted to
                            # hack us.
                            user_id=response_id,
                        )
                    )
                    return
                if (auth := session.get("auth")) is None:
                    logger.warning(
                        format_parameterized_log_message(
                            "Received message from session without auth",
                            session_id=session_id,
                        )
                    )
                    return

                session = self._session_class(session_id, auth, user, self)
                return await getattr(session, name)(*args, **kwargs)

        return handler

    async def on_connect(self, session_id, _environ, auth) -> False:
        if (response_id := auth.get("token")) is None:
            logger.warning(
                format_parameterized_log_message(
                    "Received message from session without user response id",
                    session_id=session_id,
                )
            )
            return False

        async with db():
            if not (user := await access.user_by_response_id(response_id)):
                logger.warning(
                    format_parameterized_log_message(
                        "Received message from session with an invalid user id",
                        session_id=session_id,
                        # It could be a security issue to print things like this,
                        # but we'd have bigger problems if someone really wanted to
                        # hack us.
                        user_id=response_id,
                    )
                )
                return False
            await self.save_session(session_id, {"id": user.id, "auth": auth})
            session = self._session_class(session_id, auth, user, self)

            if hasattr(session, "on_connect"):
                return await session.on_connect()
