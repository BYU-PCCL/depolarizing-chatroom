import html
import json
import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Set, Dict, Callable, Any, Optional

import jinja2
import jinja2.defaults
import jinja2.nodes
from pydantic import BaseModel
from fastapi.requests import Request

from .. import app, suggest_rephrasings as sr

DEFAULT_JINJA_NAMES = set(
    {
        **jinja2.defaults.DEFAULT_FILTERS,
        **jinja2.defaults.DEFAULT_TESTS,
        **jinja2.defaults.DEFAULT_NAMESPACE,
    }
)


class ParseTemplateBody(BaseModel):
    template: str
    value: str


@dataclass
class PromptTemplate:
    template: jinja2.Template
    default_names: Set[str]
    static_names: Set[str]
    filter_names: Set[str]


class UndefinedTemplateNameError(Exception):
    pass


def listify(fn, value):
    # run fn on value if it is a string, or run it over each element of value if it
    # is a list
    if isinstance(value, list):
        return map(fn, value)
    return fn(value)


class TemplateManager:
    _root: PromptTemplate
    _templates: Dict[str, PromptTemplate]
    _filters: Dict[str, Callable[..., Any]]
    _errors: Dict[str, Optional[str]]

    def __init__(self, root: str, templates: Dict[str, str]):
        self._environment = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)

        self._templates, self._errors = self._parse_templates_caught(templates)

        try:
            self._root = self._parse_template(root)
        except jinja2.TemplateSyntaxError as e:
            self._root = None
            self._errors["root"] = str(e)

    def _render_template(self, template: PromptTemplate, data: Any):
        # TODO: Set this up so it preserves the environments we create and just subs in
        #  the new data. Would really like it if I could just collapse the environments
        #  into each other. Just flatten them. Seems like I could. I'd just have to
        #  figure out what parts of things I could pre-compute. I wonder how I could
        #  apply operations to things.
        #  We really only need to get operations on `data` working. But this seems like
        #  more work than I can justify.

        static_templates = {}

        for sub_template_name in template.static_names:
            if sub_template_name not in self._templates:
                raise UndefinedTemplateNameError(sub_template_name)
            sub_template = self._templates[sub_template_name]
            static_templates[sub_template_name] = self._render_template(
                sub_template, data
            )

        return html.unescape(
            self._environment.from_string(template.template).render(
                **static_templates, data=data
            )
        )

    def render(self, data: Any):
        self._build_filters()
        return self._render_template(self._root, data)

    def _filter_render_fn(self, template: PromptTemplate):
        return partial(listify, partial(self._render_template, template))

    def _build_filters(self):
        for name, template_ in self._templates.items():
            self._environment.filters[name] = self._filter_render_fn(template_)

    @staticmethod
    def parse_template(
        template: str, environment: jinja2.Environment
    ) -> PromptTemplate:
        """
        Methods that call this should handle TemplateSyntaxError.
        """
        parsed_template = environment.parse(template)
        nodes = parsed_template.find_all((jinja2.nodes.Name, jinja2.nodes.Filter))
        static_names = set()
        filter_names = set()
        for n in nodes:
            (static_names if isinstance(n, jinja2.nodes.Name) else filter_names).add(
                n.name
            )
        default_names = ((static_names | filter_names) & DEFAULT_JINJA_NAMES) | {"data"}
        static_names -= default_names
        filter_names -= default_names
        # env.filters["v"] = partial(listify, fn=example_filter)
        # print(env.from_string(result).render(test2=["test", "a", "b"], test="bob"))
        # return (parsed_template=result, default_names=default_names, names=user_names)
        return PromptTemplate(
            parsed_template, default_names, static_names, filter_names
        )

    def _parse_template(self, template: str) -> PromptTemplate:
        return self.parse_template(template, self._environment)

    def _parse_templates_caught(self, templates: Dict[str, str]):
        errors = {}
        parsed_templates = {}
        for key, value in templates.items():
            parsed_template = None
            try:
                parsed_template = self._parse_template(value)
            except jinja2.TemplateSyntaxError as e:
                errors[key] = str(e)
            parsed_templates[key] = parsed_template
        return parsed_templates, errors

    def template(self, name: str) -> PromptTemplate:
        return self._templates[name]

    def set_template(self, name: str, template: str):
        self._templates[name] = self._parse_template(template)

    @property
    def root(self) -> PromptTemplate:
        return self._root

    def set_root(self, template: str):
        self._root = self._parse_template(template)

    @property
    def errors(self) -> Dict[str, Optional[str]]:
        return self._errors


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


@app.get("/template/preview/{user_id}")
def template(user_id):
    user_data = load_user_template(user_id)

    template_manager = TemplateManager(user_data["root"], user_data["templates"])

    if errors := template_manager.errors:
        return {"errors": errors}

    response = template_manager.render(
        [item for item in user_data["data"] if item["visible"]]
    )
    return {"preview": response}


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

    prompt = template_manager.render(user_data["data"])
    responses, _ = sr.collect_rephrasings(sr.rephrasings_generator(prompt, n=3))
    return {"completions": responses}
