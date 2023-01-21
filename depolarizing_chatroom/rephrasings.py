import asyncio
import os
from collections import defaultdict
from concurrent.futures import Executor
from typing import Tuple

import numpy as np
import openai

from depolarizing_chatroom.constants import MAX_REPHRASING_ATTEMPTS
from depolarizing_chatroom.data.template import (
    HorribleConfusingListWrapperThatMakesTemplateAccessPatternWork,
)
from depolarizing_chatroom.logger import logger

if OPENAPI_API_KEY := os.getenv("OPENAI_API_KEY"):
    openai.api_key = OPENAPI_API_KEY
else:
    with open("OPENAI_API_KEY.txt", "r") as f:
        openai.api_key = f.read().strip()


# These biases are @tsor13's work, ask him for more info
STRATEGY_LOGIT_BIASES = {
    "restate": {
        "1833": -1.5,  # ' understand'
        "766": -0.5,  # ' see'
        "460": -0.5,  # ' can'
        "40": -1,  # 'I'
        "3285": -0.5,  # ' hear'
        "2396": -1.25,  # 'So'
    },
    "validate": {
        "1026": -2,  # 'It'
    },
    "clarify": {
        "6090": -1.25,  # 'Can'
        "23722": -0.5,  # 'Could'
        "5195": -0.25,  # 'Why'
        "5211": -0.5,  # 'Do'
    },
    "polite": {
        "40": -2.5,  # 'I'
        "12546": -0.5,  # ' disagree'
    },
}

BASE_LOGIT_BIASES = {
    "31699": -3,  # 'fuck'
    "5089": -3,  # ' fuck'
    "9372": -3,  # ' fucking'
    "542": -3,  # 'ass'
    "840": -3,  # ' ass'
    "5968": -3,  # ' hell'
}


def rephrasings_generator(prompt, n=1, logit_bias=None, request_logprobs=False):
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=prompt,
        max_tokens=400,
        top_p=0.95,
        stream=True,
        n=n,
        logprobs=3 if request_logprobs else None,
        logit_bias=logit_bias or {},
    )

    response_text = ""
    for item in response:
        response_choice = item.choices[0]
        rephrasing = response_choice.text
        response_text += rephrasing

        if request_logprobs:
            logprob = np.round(
                np.exp(next(iter(response_choice.logprobs.top_logprobs[0].values()))), 2
            )
            yield (response_choice.index, rephrasing), logprob
        else:
            yield (response_choice.index, rephrasing)


def collect_rephrasings(rephrasing_generator):
    rephrasings = defaultdict(list)
    logprobs = defaultdict(list)
    for first, second in rephrasing_generator:
        logprob = None
        if hasattr(first, "__len__") and len(first) == 2:
            index, rephrasing = first
            logprob = second
        else:
            index, rephrasing = first, second
        rephrasings[index].append(rephrasing)
        if logprob is not None:
            logprobs[index].append(logprob)
    rephrasing_strings = ["".join(value).rstrip('"') for value in rephrasings.values()]
    return rephrasing_strings, list(logprobs.values())


def generate_rephrasing_task(prompt, strategy) -> Tuple[str, str]:
    response = None
    for i in range(MAX_REPHRASING_ATTEMPTS):
        try:
            (response,), _ = collect_rephrasings(
                rephrasings_generator(
                    prompt,
                    logit_bias={
                        **(STRATEGY_LOGIT_BIASES.get(strategy, {})),
                        **BASE_LOGIT_BIASES,
                    },
                    n=1,
                )
            )
            break
        except Exception:
            logger.exception("Error generating rephrasings")
    return strategy, response


async def generate_rephrasings(executor: Executor, templates, turns):
    prompts = {
        strategy: template.render(
            HorribleConfusingListWrapperThatMakesTemplateAccessPatternWork(turns)
        )
        for (strategy, template) in templates.items()
    }

    # Run in executor to avoid blocking the event loop
    return dict(
        await asyncio.gather(
            *[
                asyncio.get_event_loop().run_in_executor(
                    executor, generate_rephrasing_task, prompt, strategy
                )
                for (strategy, prompt) in prompts.items()
            ]
        )
    )


def print_single_rephrasing_response(response) -> None:
    all_probs = []
    print("✨✨✨")
    has_probs = False
    for item in response:
        if has_probs := len(item[0]) == 2:
            (_, item), probs = item
            all_probs.append(probs)
        else:
            _, item = item
        print(item, end="")

    print("✨✨✨")

    if has_probs:
        print()
        print(tuple(all_probs[:3]))
