from datetime import datetime
from typing import Union

from fastapi import Depends, HTTPException
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.datastructures import MultiDict

from . import app
from .. import (
    DataAccess,
    very_insecure_session_auth_we_know_the_risks,
    templates,
    get_data_access,
    access,
)
from ..data import models


def validate_code(code, access) -> Union[models.Code, bool]:
    c = access.session.query(models.Code).filter_by(code=code).first()
    if c is not None:
        if c.expiry > datetime.now():
            return c

    return False


def store_response(access: DataAccess, form, u, qtype, qnum, is_post) -> bool:
    # TODO: Make sure form is passed in as dict even if Pydantic is used to validate
    r = models.Response(is_post=is_post)
    r.user_id = u.id
    r.question_id = u.code.questions[
        qnum - 1
    ].id  # get question id from user's associated code
    r.code_id = u.code.id
    if qtype == "grid":
        # join each response with semicolon to list
        res = []
        for k, v in form.items():
            res.append(f"{k};{v}")
        r.response = res
    else:
        print("response ", list(form.values()))
        if qtype == "multiple":
            vals = list(form.values())[0]
        else:
            vals = list(form.values())
        r.response = vals

    # radio will only have one response
    access.add_to_db(r)
    print(r)
    return True


@app.get("/")
def home(
    request: Request,
    _: None = Depends(very_insecure_session_auth_we_know_the_risks),
    access: DataAccess = Depends(get_data_access),
) -> Union[HTMLResponse, RedirectResponse]:
    u = (
        access.session.query(models.User)
        .filter_by(email=request.session["user"]["email"])
        .first()
    )
    # redirect user wherever they need to go

    if u.status == "survey":
        return templates.TemplateResponse(
            "question_resume.html",
            dict(
                request=request, json=get_question(u.code.code, u.curq, False, u.email)
            ),
        )
    elif u.status == "chatroom":
        return RedirectResponse(f"/chatroom/{u.chatroom_id}")
    elif u.status == "waiting":
        return RedirectResponse(f"/waiting_room/{u.id}")
    elif u.status == "postsurvey":
        return templates.TemplateResponse(
            "question_resume.html",
            dict(
                request=request,
                json=get_question(u.code.code, u.curq, True, {}),
                is_post=True,
            ),
        )

    return templates.TemplateResponse(
        "index.html", dict(request=request, popup="popup.html")
    )


@app.get("/thank-you", response_class=HTMLResponse)
def thank_you():
    return "<h1>Thank you</h1>"


@app.post("/ajax-form")
async def home_form(
    calling_this_request_temp__: Request, access: DataAccess = Depends(get_data_access)
) -> Union[HTMLResponse, dict]:
    # TODO: Not sure what "home form" means here
    u = (
        access.session.query(models.User)
        .filter_by(email=calling_this_request_temp__.session["user"]["email"])
        .first()
    )
    # if code in form, validate and begin survey
    form = await calling_this_request_temp__.form()

    if "code" in form:
        code = form["code"]
        # get code response
        c = validate_code(code, access)
        if not c:
            raise HTTPException(detail="Invalid code", status_code=400)

        # assign user the code
        u.code = c
        # VINHOWE TEST CHANGES SO WE CAN MESS WITH GPT3
        u.status = "chatroom"
        access.commit()
        # store cookie
        calling_this_request_temp__.session["user"]["code"] = code

        # start survey
        return {"redirect": f"/waiting_room/{u.id}"}

    # otherwise, if qtype is in the form, it's a question
    elif "qtype" in form:
        # Apparently starlette's FormData is an ImmutableMultiDict, so we wrap it in a
        # MultiDict—fingers crossed
        form = MultiDict(form)
        qtype = form.pop("qtype")
        # if form type is multiple
        if qtype == "multiple":
            qname = list(form.keys())[0]
            print(form.getlist(qname))
            form[qname] = form.getlist(qname)
        print(f"storing response {u.curq}")
        store_response(form, u, qtype, u.curq, ("is_post" in form))

        # update user
        u.curq += 1
        access.commit()

        return get_question(u.code.code, u.curq, form.get("is_post", False))

    raise HTTPException(status_code=401, detail="Invalid submission - no form data")


def get_question(code, qnum, is_post, email) -> Union[HTMLResponse, dict]:
    """
    code: str, survey code
    qnum: int, # question user is on (1 is first)
        * if qnum is out of range, return chatroom
    """
    # get question
    c = access.session.query(models.Code).filter_by(code=code).first()
    q = (
        access.session.query(models.Question)
        .filter_by(number=qnum, code_id=c.id, is_post=is_post)
        .first()
    )

    # if no question, either redirect to finish or waiting room
    if q is None:
        # get user
        u = access.session.query(models.User).filter_by(email=email).first()

        # update user
        u.status = "waiting"
        access.commit()

        return {"redirect": f"/waiting_room/{u.id}"}

    # otherwise, determine if is last question
    if len(c.questions) == qnum:
        submit = "Finish!"
    else:
        submit = "Next Question:"

    # parse question
    qd = q.__dict__
    qt = q.type
    if qt == "slider":
        qd["min_val"] = q.range[0]
        qd["max_val"] = q.range[1]
    elif qt == "grid":
        # distribute questions
        qs = q.questions
        qd["questions"] = qs
        qd["rows"] = list(range(len(qs)))
        # distribute options
        opts = q.options
        qd["opts"] = opts
        qd["labels"] = (opts[0], opts[-1])
    else:
        qd["opts"] = q.options

    return {
        "question": q.question,
        "type": qt,
        "submit": submit,
        "is_post": is_post,
        "rendered_form": templates.TemplateResponse("question_bs.html", qd),
    }
