import os
from os import path

# import eventlet
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_socketio import SocketManager
from starlette.middleware.sessions import SessionMiddleware

from .data import models
from .data.crud import DataAccess, TestDataAccess
from .data.database import engine, SessionLocal
from .exceptions import AuthException
from .util import format_dt

load_dotenv(path.join(path.dirname(__file__), ".env"))

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
templates.env.globals.update(zip=zip)
templates.env.globals.update(int=int)
templates.env.filters["format_dt"] = format_dt

app.add_middleware(
    SessionMiddleware, secret_key=os.getenv("SECRET_KEY") or "default-secret"
)

socket_manager = SocketManager(app=app)


def get_db() -> SessionLocal:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


access: DataAccess = None


@app.on_event("startup")
async def startup_event():
    global access
    access = DataAccess(next(get_db()))
    TestDataAccess(access.session).initialize_chat_test()


# TODO: This isn't very useful if we just define a global. Looks like we can't use
#  FastAPI dependency injection with socketio—at least not yet.
def get_data_access() -> DataAccess:
    return access


def very_insecure_session_auth_we_know_the_risks(request: Request):
    if not request.session.get("user"):
        raise AuthException()


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
