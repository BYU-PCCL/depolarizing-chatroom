import html
import json
import re
from pathlib import Path
from typing import Any, Dict

from fastapi.requests import Request
from pydantic import BaseModel

from .. import rephrasings as sr
from ..data.template import (
    HorribleConfusingListWrapperThatMakesTemplateAccessPatternWork,
)
from ..rephrasings import BASE_LOGIT_BIASES, STRATEGY_LOGIT_BIASES
from ..server import TemplateManager, app
from ..util import calculate_turns, last_n_turns


class ParseTemplateBody(BaseModel):
    template: str
    value: str


def load_default_template() -> Dict[str, Any]:
    with open("template.json") as f:
        template_data = json.load(f)

    return template_data["default"]


def user_template_filepath(user_id):
    filename = re.sub(r"[\W_]+", "", user_id).lower() + ".json"
    return Path(filename)


def load_user_template(user_id: str) -> Dict[str, Any]:
    user_filepath = user_template_filepath(user_id)

    if not user_filepath.exists():
        return load_default_template()

    with open(user_filepath) as f:
        return json.load(f)


def save_user_template(user_id: str, data: Dict[str, Any]) -> None:
    user_filepath = user_template_filepath(user_id)

    with open(user_filepath, "w") as f:
        json.dump(data, f)


@app.get("/template/{user_id}")
def template(user_id):
    return load_user_template(user_id)


@app.patch("/template/{user_id}")
async def patch_template(user_id, request: Request):
    user_data = load_user_template(user_id)
    request_body = await request.json()
    # deeply html.unescape all strings in user_data
    user_data = html.unescape(json.dumps(user_data))
    user_data = json.loads(user_data)
    user_data = {**user_data, **request_body}
    save_user_template(user_id, user_data)


@app.get("/template/example-data")
def template():
    with open("example-data.json") as f:
        return json.load(f)


def render_template(template_manager: TemplateManager, data: Any) -> str:
    data = [item for item in data["data"] if item["visible"]]

    (
        turn_count,
        user_turn_count,
        partner_turn_count,
        last_turn_counted,
        turns,
    ) = calculate_turns(data, data[-1]["position"])

    template_turns = last_n_turns(turns, 10)

    return template_manager.render(
        HorribleConfusingListWrapperThatMakesTemplateAccessPatternWork(template_turns)
    )


@app.get("/template/preview/{user_id}")
def template(user_id):
    user_data = load_user_template(user_id)

    template_manager = TemplateManager(user_data["root"], user_data["templates"])

    if errors := template_manager.errors:
        return {"errors": errors}

    return {"preview": render_template(template_manager, user_data)}


@app.post("/template/parse/{user_id}")
def template(user_id, body: ParseTemplateBody):
    user_data = load_user_template(user_id)
    is_root = body.template == "root"
    templates = user_data["templates"]

    if not is_root:
        templates[body.template] = body.value

    template_manager = TemplateManager(
        body.value if is_root else user_data["root"], templates
    )

    if errors := template_manager.errors:
        return {"errors": errors}

    if is_root:
        template = template_manager.root
        user_data["root"] = body.value
    else:
        template = template_manager.template(body.template)
        user_data["templates"][body.template] = body.value

    save_user_template(user_id, user_data)

    # try:
    #     parsed_template = TemplateManager.parse_template(
    #         body.value, jinja2.Environment()
    #     )
    # except jinja2.TemplateSyntaxError as e:
    #     return {"error": str(e)}
    return dict(
        default_names=list(template.default_names),
        names=template.static_names | template.filter_names,
    )


@app.get("/template/completions/{user_id}")
def template(user_id):
    user_data = load_user_template(user_id)

    template_manager = TemplateManager(user_data["root"], user_data["templates"])

    if errors := template_manager.errors:
        return {"errors": errors}

    prompt = render_template(template_manager, user_data)
    responses, _ = sr.collect_rephrasings(sr.rephrasings_generator(prompt, n=3))
    sr.rephrasings_generator(
        prompt,
        logit_bias={
            **(STRATEGY_LOGIT_BIASES.get(user_id, {})),
            **BASE_LOGIT_BIASES,
        },
        n=1,
    )
    return {"completions": responses}
