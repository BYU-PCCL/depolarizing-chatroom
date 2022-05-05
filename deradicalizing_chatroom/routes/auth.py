from fastapi import Depends, HTTPException, Form
from fastapi.requests import Request
from fastapi.responses import HTMLResponse

from .. import app, templates, DataAccess, get_data_access


@app.get("/signup")
def signup(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("signup_bs.html", dict(request=request))


@app.get("/login")
def login(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login_bs.html", dict(request=request))


@app.post("/login")
def post_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    access: DataAccess = Depends(get_data_access),
) -> dict:
    # TODO: if change login logic (e.g. password) will need to change
    #  if logging in, check if email is real

    if not (user := access.process_login(email, password)):
        raise HTTPException(
            status_code=400, detail="Invalid sign in. Confirm email and password"
        )

    # Set cookie
    request.session["user"] = {"email": email, "username": user.username}

    return {"redirect": "/"}


@app.post("/signup")
def post_signup(
    email: str = Form(...),
    username: str = Form(...),
    affiliation: str = Form(...),
    password: str = Form(...),
    access: DataAccess = Depends(get_data_access),
) -> dict:
    # if processing signup fails, redirect to login
    if not access.process_signup(email, username, affiliation, password):
        raise HTTPException(status_code=400, detail="Email or username already taken.")

    return {"redirect": "/"}
