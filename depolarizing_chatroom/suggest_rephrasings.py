import os
import re
from collections import defaultdict

import numpy as np
import openai

if OPENAPI_API_KEY := os.getenv("OPENAI_API_KEY"):
    openai.api_key = OPENAPI_API_KEY
else:
    with open("OPENAI_API_KEY.txt", "r") as f:
        openai.api_key = f.read().strip()


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
    print("✨✨✨ PROMPT ✨✨✨")
    print(prompt)
    print("✨✨✨ END PROMPT ✨✨✨")
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=prompt,
        max_tokens=400,
        # temperature=1,
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


def print_single_rephrasing_response(response):
    all_probs = []
    print("✨✨✨")
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
