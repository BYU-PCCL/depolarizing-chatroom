import asyncio
import enum
import multiprocessing
import os
import random
import time
import uuid
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp
import pytest
import pytest_asyncio
import socketio
import uvicorn
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request

import depolarizing_chatroom.data.models as models
import depolarizing_chatroom.server

WAITING_ROOM_NAMESPACE = "/waiting-room"
CHATROOM_NAMESPACE = "/chatroom"


class DumbProfilerMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        method = request.method
        path = request.url.path

        begin = time.perf_counter()
        await self.app(scope, receive, send)
        end = time.perf_counter()
        # Time formatted in ss:ms
        formatted = f"{end - begin:.2f}"
        print(f"Method: {method}, Path: {path}, Time: {formatted}")


SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://localhost:5432/chatroom"
# SQLITE_TESTING_DB_PATH = "testing.sqlite3"
# SQLALCHEMY_DATABASE_URL = f"sqlite+aiosqlite:///{SQLITE_TESTING_DB_PATH}"


class MultiprocessUvicornServer(multiprocessing.Process):
    def __init__(
        self,
        config: uvicorn.Config,
        server_number: int,
        semaphore: multiprocessing.Semaphore,
    ):
        super().__init__(daemon=True)
        self._uvicorn_config = config
        self._server_number = server_number
        self._semaphore = semaphore
        self._server = None

    def stop(self) -> None:
        self.terminate()

    def run(self, *args, **kwargs) -> None:
        os.environ["DB_URI"] = SQLALCHEMY_DATABASE_URL
        # engine = create_async_engine(
        #     SQLALCHEMY_DATABASE_URL
        #     # SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        # )
        #
        # testing_session_local = sessionmaker(
        #     autocommit=False, autoflush=False, bind=engine
        # )
        #
        # def get_db_wrapped() -> Generator[sessionmaker, None, None]:
        #     session = testing_session_local()
        #     try:
        #         yield session
        #     finally:
        #         session.close()
        #
        # depolarizing_chatroom.server.app.dependency_overrides[
        #     depolarizing_chatroom.server.get_db
        # ] = get_db_wrapped
        #
        # depolarizing_chatroom.server.get_db = get_db_wrapped

        @depolarizing_chatroom.server.app.on_event("startup")
        def release_semaphore() -> None:
            self._semaphore.release()

        # depolarizing_chatroom.server.app.add_middleware(DumbProfilerMiddleware)
        # depolarizing_chatroom.server.app.add_middleware(
        #     SQLAlchemyMiddleware,
        #     db_url=SQLALCHEMY_DATABASE_URL,
        #     engine_args={
        #         # ONLY FOR TESTING OH MY GOD DO NOT USE THIS IN PRODUCTION
        #         "echo": True,
        #         "check_same_thread": False,
        #     }
        # )

        server = uvicorn.Server(config=self._uvicorn_config)
        server.run()


@pytest_asyncio.fixture(name="_mock_db")
async def fixture_mock_db() -> None:
    # if (db_path := Path(SQLITE_TESTING_DB_PATH)).exists():
    #     db_path.unlink()
    engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
    async with engine.begin() as connection:
        # await connection.run_sync(models.Base.metadata.drop_all)
        await connection.run_sync(models.Base.metadata.create_all)


@pytest_asyncio.fixture(name="mock_servers")
async def fixture_mock_servers(_mock_db) -> List[str]:
    servers = []
    server_count = 10
    semaphore = multiprocessing.Semaphore()
    for i, port in enumerate(range(8000, 8000 + server_count)):
        config = uvicorn.Config(
            "depolarizing_chatroom.server:app",
            log_config="uvicorn-log-config.yml",
            # access_log=False,
            port=port,
        )
        server = MultiprocessUvicornServer(config, i, semaphore)
        server.start()
        servers.append((server, f"http://localhost:{port}/"))
        servers.append((None, f"http://localhost:{port}/"))
        servers.append((None, f"http://localhost:{port}/"))

    # wait for all servers to start
    for _ in range(server_count):
        semaphore.acquire()

    # Add a little delay just for the sick thrill of it
    await asyncio.sleep(1)

    yield [url for _, url in servers]
    for server, url in servers:
        server.stop()


@pytest_asyncio.fixture(name="single_mock_server")
async def fixture_single_mock_server(_mock_db) -> str:
    port = 8090
    semaphore = multiprocessing.Semaphore()
    config = uvicorn.Config(
        "depolarizing_chatroom.server:app",
        log_config="uvicorn-log-config.yml",
        # access_log=False,
        port=port,
    )
    server = MultiprocessUvicornServer(config, 0, semaphore)
    server.start()
    semaphore.acquire()
    await asyncio.sleep(3)
    yield f"http://localhost:{port}/"
    server.stop()


@pytest_asyncio.fixture(name="client_session")
async def fixture_client_session() -> AsyncGenerator[aiohttp.ClientSession, None]:
    async with aiohttp.ClientSession() as session:
        yield session


class TestUserPage(str, enum.Enum):
    INTRO = "intro"
    WAITING = "waiting"
    VIEW = "view"
    TUTORIAL = "tutorial"
    CHATROOM = "chatroom"


async def post_signup(url, session, position) -> str:
    token = uuid.uuid4().hex
    response = await session.post(
        url + "signup", json={"respondentId": token, "position": position.value}
    )
    assert response.status == 200
    return token


async def post_initial_view(url, session, token, view) -> None:
    response = await session.post(
        url + "initial-view", json={"view": view}, headers={"X-AUTH-CODE": token}
    )
    assert response.status == 200


async def get_user(url, session, token) -> Dict[str, Any]:
    response = await session.get(url + "user", headers={"X-AUTH-CODE": token})
    return await response.json()


async def get_waiting_status(
    url, session: aiohttp.ClientSession, token
) -> aiohttp.ClientResponse:
    return await session.get(url + "waiting-status", headers={"X-AUTH-CODE": token})


async def connect_to_waiting_room(
    url, token, callback=None, wait_for_redirect=False, timeout=10
) -> Optional[Dict[str, Any]]:
    sio = socketio.AsyncClient()
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    @sio.event(namespace=WAITING_ROOM_NAMESPACE)
    async def redirect(data) -> None:
        future.set_result(data)

    @sio.event(namespace=WAITING_ROOM_NAMESPACE)
    async def matched_with(ids) -> None:
        user_id, matched_with_id = ids
        print(f"{user_id} matched with {matched_with_id}")

    await sio.connect(
        url,
        socketio_path="/ws/socket.io",
        wait_timeout=10,
        namespaces=WAITING_ROOM_NAMESPACE,
        auth={"token": token},
    )

    timeout_task = None
    if timeout is not None:
        # Set up timeout w/ exception details
        async def timeout_callback() -> None:
            await sio.disconnect()
            future.set_exception(
                TimeoutError(f"Timed out after {timeout} seconds in waiting room")
            )

        timeout_task = asyncio.create_task(asyncio.sleep(timeout))
        timeout_task.add_done_callback(lambda _: timeout_callback())

    if callback:
        if asyncio.iscoroutine(callback):
            await callback

        else:
            callback()

    try:
        if wait_for_redirect:
            redirect_data = await future
            return redirect_data
    finally:
        if timeout_task is not None:
            timeout_task.cancel()
        await sio.disconnect()


@asynccontextmanager
async def chatroom(url, token):
    sio = socketio.AsyncClient()

    @asynccontextmanager
    async def session():
        await sio.connect(
            url,
            socketio_path="/ws/socket.io",
            wait_timeout=10,
            namespaces=CHATROOM_NAMESPACE,
            auth={"token": token},
        )
        try:
            yield
        finally:
            await sio.disconnect()

    # Wrap sio.event so that we don't have to provide a namespace
    sio.event = partial(sio.event, namespace=CHATROOM_NAMESPACE)

    yield sio, session


async def mock_user_match(url, session, position, i) -> str:
    token = await post_signup(url, session, position)

    # Get user ID
    user = await get_user(url, session, token)

    # Connect to waiting room, just waiting for a redirect to /view
    redirect = await connect_to_waiting_room(url, token, wait_for_redirect=True)
    assert redirect["to"] in ("view", "tutorial"), f"User {i} got {redirect}"

    # Connect to waiting room and post view with callback
    await connect_to_waiting_room(
        url,
        token,
        # TODO: It hurts Grant's eyes
        callback=post_initial_view(url, session, token, "view"),
    )

    # Race condition here, wait like a second
    await asyncio.sleep((random.random() * 1) + 1)

    waiting_status = await get_waiting_status(url, session, token)
    # Get waiting room status, make sure there was no 500 error
    assert waiting_status.status == 200

    # Connect to waiting room and wait for redirect to /chatroom
    redirect = await connect_to_waiting_room(url, token, wait_for_redirect=True)
    assert redirect["to"] + str(user["id"]) == "chatroom" + str(
        user["id"]
    ), f"User {user['id']} got {redirect}"

    # Assert stuff about the user
    # TODO: Assert why are we doing this
    waiting_status = await get_waiting_status(url, session, token)
    # Get waiting room status, make sure there was no 500 error
    assert waiting_status.status == 200

    return token


async def mock_user_chatter(url, session, position, i) -> None:
    await asyncio.sleep(i * 1.5)
    try:
        # Wait to match first
        token = await mock_user_match(url, session, position, i)
    except asyncio.TimeoutError:
        print(f"User {i} timed out while waiting")
        # We're going to be forgiving here
        return

    # Connect to chatroom
    async with chatroom(url, token) as (sio, session):
        # Register event handlers
        @sio.event
        async def connect() -> None:
            print(f"User {i} connected to chatroom")

        @sio.event
        async def disconnect() -> None:
            print(f"User {i} disconnected from chatroom")

        @sio.event
        async def message(data) -> None:
            print(f"User {i} got message {data}")

        async with session():

            async def type_regularly() -> None:
                while True:
                    await sio.emit("typing", namespace=CHATROOM_NAMESPACE)
                    await asyncio.sleep(5)

            async def type_then_send_messages_continuously() -> None:
                while True:
                    await asyncio.sleep(5 + (random.random() * 15))
                    typing_task = asyncio.create_task(type_regularly())
                    typing_time = 5 + (random.random() * 5)
                    await asyncio.sleep(typing_time)
                    typing_task.cancel()
                    await sio.emit(
                        "message",
                        {"body": " ".join(str(uuid.uuid4()).split("-"))},
                        namespace=CHATROOM_NAMESPACE,
                    )

            # await asyncio.gather(type_continuously(), send_messages_periodically())
            await type_then_send_messages_continuously()


@pytest.mark.asyncio
async def test_signup_user(single_mock_server, client_session) -> None:
    respondent_id = "test_respondent_id"
    position = "oppose"
    signup_body = {"respondentId": respondent_id, "position": position}

    async with client_session.post(
        single_mock_server + "signup", json=signup_body
    ) as response:
        assert response.status == 200, "Signup failed"

    # Test that user is seen in server 1
    async with client_session.get(
        single_mock_server + "user", headers={"X-AUTH-CODE": respondent_id}
    ) as response:
        # Get response body
        response_body = await response.json()
        assert (
            response_body["response_id"] == respondent_id
        ), "Respondent ID doesn't match provided respondent ID"
        assert (
            response_body["position"] == "oppose"
        ), "Position doesn't match provided position"
        # TODO: Make sure to check this after setting the user treatment
        assert (
            response_body["post_survey_url"]
            == f'{os.getenv("POST_CHAT_URL")}?RESPONDENT_ID={respondent_id}&treatment'
            f"=&position={position}"
        ), "Post survey URL doesn't match expected URL"
        assert (
            response_body["no_chat_url"]
            == f'{os.getenv("NO_CHAT_URL")}?RESPONDENT_ID={respondent_id}&position='
            f"{position}"
        ), "No chat survey URL doesn't match expected URL"

    async with client_session.post(
        single_mock_server + "signup", json=signup_body
    ) as response:
        assert response.status == 200, "Signup with existing user didn't fail quietly"

    # Provide leave reason
    leave_reason = "test_leave_reason"
    leave_body = {"leaveReason": leave_reason}
    async with client_session.put(
        single_mock_server + "user",
        json=leave_body,
        headers={"X-AUTH-CODE": respondent_id},
    ) as response:
        assert response.status == 200, "Setting leave reason failed"


@pytest.mark.asyncio
async def test_match_users(mock_servers, client_session) -> None:
    user_positions = [models.UserPosition.SUPPORT, models.UserPosition.OPPOSE] * (
        500 // 2
    )
    random.shuffle(user_positions)
    await asyncio.gather(
        *[
            mock_user_match(
                random.choice(mock_servers), client_session, user_position, i
            )
            for i, user_position in enumerate(user_positions)
        ]
    )


@pytest.mark.asyncio
async def test_chatter(mock_servers, client_session) -> None:
    user_positions = [models.UserPosition.SUPPORT, models.UserPosition.OPPOSE] * (
        500 // 2
    )
    random.shuffle(user_positions)
    await asyncio.gather(
        *[
            mock_user_chatter(
                mock_servers[i % len(mock_servers)], client_session, user_position, i
            )
            for i, user_position in enumerate(user_positions)
        ]
    )
