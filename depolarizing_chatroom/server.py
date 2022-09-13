import os
from os import path
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from fastapi_socketio import SocketManager
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.security import APIKeyHeader

from .data import models
from .data.crud import DataAccess
from .data.database import engine, SessionLocal
from .data.template import load_templates_from_directory, TemplateManager
from .exceptions import AuthException

load_dotenv(path.join(path.dirname(__file__), ".env"))

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    SessionMiddleware, secret_key=os.getenv("SECRET_KEY") or "default-secret"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_manager = SocketManager(app=app, cors_allowed_origins=[])

templates = load_templates_from_directory(os.getenv("TEMPLATES_DIR"))
executor = None


_API_KEY_NAME = "X-AUTH-CODE"
_api_key_header = APIKeyHeader(name=_API_KEY_NAME, auto_error=False)


def get_db() -> SessionLocal:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@app.on_event("startup")
async def startup_event():
    # TestDataAccess(get_data_access().session).initialize_waiting_room_test()
    pass


def get_data_access() -> DataAccess:
    return DataAccess(next(get_db()))


def get_templates() -> Dict[str, TemplateManager]:
    return templates


def very_insecure_session_auth_we_know_the_risks(request: Request):
    if not request.session.get("user"):
        raise AuthException()


async def get_user_from_auth_code(
    header_key: str = Depends(_api_key_header),
    access: DataAccess = Depends(get_data_access),
):
    """
    Based on the example at
    https://fastapi.tiangolo.com/advanced/security/http-basic-auth/#check-the-username
    :raises HTTPException: if credentials are incorrect:
    """

    if header_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user = access.session.query(models.User).filter_by(response_id=header_key).first()
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


from . import routes


