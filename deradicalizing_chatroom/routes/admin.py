from os import environ
from typing import Optional

from fastapi import Depends, Form
from fastapi.datastructures import FormData
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from .. import app, templates, DataAccess
from .. import get_data_access
from ..data import models
from ..exceptions import AdminAuthException


def admin_auth(request: Request):
    """
    extra security for admin items
    """

    if not request.session.get("admin"):
        raise AdminAuthException()


@app.exception_handler(AdminAuthException)
async def admin_auth_exception_handler(*_) -> RedirectResponse:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: TODO: TODO:
    # TODO: Add a parameter to specify the redirect return URL
    return RedirectResponse("/admin/login")


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "admin_login.html", dict(request=request, incorrect=False)
    )


@app.post("/admin/login")
def post_admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username == environ.get("ADMIN_USERNAME") and password == environ.get(
        "ADMIN_PW"
    ):
        request.session["admin"] = True
        return RedirectResponse("/admin")

    return templates.TemplateResponse(
        "admin_login.html", dict(request=request, incorrect=True)
    )


@app.get("/survey-builder")
def survey_builder(request: Request, _: None = Depends(admin_login)) -> HTMLResponse:
    return templates.TemplateResponse(
        "survey_builder.html", dict(request=request, code=None)
    )


@app.post("/survey-builder")
async def post_survey_builder(
    request: Request,
    code: str = Form(...),
    qnum: int = Form(...),
    expiry: Optional[str] = Form(None),
    access: DataAccess = Depends(get_data_access),
    _: None = Depends(admin_login),
) -> HTMLResponse:
    if expiry:
        code = code
        # look up code in db
        c = access.session.query(models.Code).filter_by(code=code).first()
        # if doesn't exist, add new code and survey, otherwise, resume
        if c is None:
            access.add_code(code, expiry)
            qnum = 1
            # start thread listening on code
            # t = threading.Thread(target=waitlist_listener, args=(code,))
            # t.setDaemon(True)
            # t.start()
            # TODO if have waitlist, add stuff
            # eventlet.spawn(waitlist_listener, code)
            print("thread started")
        else:
            qnum = len(c.questions) + 1
        print("rendering question")
        return templates.TemplateResponse(
            "survey_builder.html", dict(request=request, code=code, qnum=qnum)
        )
    else:
        # or adding new question
        code = code
        qnum = qnum
        code, qnum = parse_question_add(code, qnum, await request.form(), access)
        return templates.TemplateResponse(
            "survey_builder.html",
            dict(
                request=request,
                code=code,
                qnum=qnum,
                is_post=("is_post" in request.form),
            ),
        )


def parse_question_add(code, n, form: FormData, access: DataAccess):
    # set question
    qtype = form["type"]
    q = models.Question(
        question=form["question"],
        type=qtype,
        number=n,
        is_post=form["is_post"],
    )

    # get code
    c = access.session.query(models.Code).filter_by(code=code).first()
    q.code_id = c.id

    # parse type
    if qtype == "radio" or qtype == "multiple":
        # options are options in list
        q.options = form["option"]
    elif qtype == "grid":
        # each row of the grid
        q.questions = form["row"]
        # options are the columns of the grid (least likely, average, most likely, etc)
        q.options = form["option"]
    else:  # else slider
        # start is where the slider should start
        q.start = form["start"]
        # range is min/max of slider
        q.range = [form["min_val"], form["max_val"]]
        # step is slider increment
        q.step = form["step"]

    # add question to database
    access.add_to_db(q)

    return code, n + 1


@app.get("/admin")
def admin(request: Request, _: None = Depends(admin_login)) -> HTMLResponse:
    tables = {"users": models.User, "chatrooms": models.Chatroom, "codes": models.Code}
    for name, table in tables.items():
        tables[name] = table.query.all()
    return templates.TemplateResponse("data.html", dict(request=request, data=tables))
