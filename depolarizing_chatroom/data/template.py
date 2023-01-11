import html
import json
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

import jinja2
import jinja2.defaults
import jinja2.nodes

DEFAULT_JINJA_NAMES = set(
    {
        **jinja2.defaults.DEFAULT_FILTERS,
        **jinja2.defaults.DEFAULT_TESTS,
        **jinja2.defaults.DEFAULT_NAMESPACE,
    }
)


@dataclass
class PromptTemplate:
    template: jinja2.Template
    default_names: Set[str]
    static_names: Set[str]
    filter_names: Set[str]


class UndefinedTemplateNameError(Exception):
    pass


class TemplateLoadingError(Exception):
    def __init__(self, errors: Dict[str, Optional[str]]):
        super().__init__(f"Failed to load templates: {json.dumps(errors, indent=2)}")
        self._errors = errors

    @property
    def exceptions(self):
        return self._errors


class HorribleConfusingListWrapperThatMakesTemplateAccessPatternWork:
    # TODO: Explain what on earth this does and why we need it because I can't remember
    def __init__(self, data_list: List[Any]):
        self._data_list = data_list

    def __getitem__(self, index) -> Union[List[Any], Any]:
        if isinstance(index, slice):
            if index.step is not None:
                raise ValueError("Steps are not supported")
            if (
                index.stop == -1
                and self._data_list
                and len(last_item := self._data_list[-1]) > 1
            ):
                data_slice = self._data_list[index]
                return data_slice + [last_item[:-1]]
            return self._data_list[index]
        elif isinstance(index, int):
            # If the index is just an integer, just return the item
            return self._data_list[index]
        else:
            raise TypeError(f"Index must be int or slice, not {type(index)}")


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
    _errors: Dict[str, str]

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


def load_template_from_from_file(file) -> TemplateManager:
    with open(file) as f:
        data = json.load(f)
    template = TemplateManager(data["root"], data["templates"])

    if template.errors:
        raise TemplateLoadingError(template.errors)

    return template


def load_templates_from_directory(directory) -> Dict[str, TemplateManager]:
    templates = {}
    for file in Path(directory).glob("*.json"):
        template = load_template_from_from_file(file)
        templates[file.stem] = template
    return templates
