import os
import re
from collections import defaultdict

import numpy as np
import openai

# from IPython.display import Markdown, display
# from tqdm import tqdm

PARTY_MAP = {"D": "Democrat", "R": "Republican"}
REVERSE_POSITION_MAP = {"Supporter": "Opponent", "Opponent": "Supporter"}


# Different warnings for different DVs.

# Conversation again
# warning_string = ("This might be a counterproductive thing to say, if these "
# "two ever hope to talk again. ")

# More sympathetic to each other's point of view

warning_string = (
    "This kind of statement might be harmful. "
    # "This might be a counterproductive thing to say, if these "
    # "two are to ever see each others' points of view. "
)

# Non-violence
# warning_string = ("This might be a counterproductive thing to say, if we want "
#                   "these two to not support political violence or a civil war in the next decade. ")

rephrasing_specs = {
    "validate": lambda position, opp_position: (
        warning_string + f"It is helpful to first validate what the other person "
        "thinks. "
        f"Can you suggest a rephrasing where the {position.lower()} first "
        f"validates what the {opp_position.lower()} said?"
    ),
    # "paraphrase_and_ask": lambda party, opp_party: (
    #     warning_string
    #     + f"Can you suggest a rephrasing of that message, where the {party} instead "
    #     f"paraphrases what the {opp_party} said last, and then asks a clarifying "
    #     f"question or question of understanding? (NOT a 'trap' question or a "
    #     f"question to make a point)"
    # ),
    # "rephrase_to_i": lambda party, opp_party: (
    #     warning_string
    #     + f"Can you suggest a rephrasing of that message, where the {party} instead "
    #     "makes a statement beginning with 'I feel that...' or 'It seems to me that' "
    #     "instead of making braod, generalizing claims?"
    # ),
    # "restate_before_disagree": lambda party, opp_party: (
    #     warning_string
    #     + f"Can you suggest a rephrasing of that message, where the {party} instead "
    #     f"restates, in their own words, the {opp_party}'s last message before "
    #     "introducing disagreement?"
    # ),
    # "empathy": lambda party, opp_party: (
    #     warning_string
    #     + f"Can you suggest a rephrasing of that message, where the {party} instead "
    #     f"emphasizes shared beliefs and values with the {opp_party}, "
    #     "essentially indicating that we all care about the same big-picture things "
    #     "rather than emphasizing the disagreement in the details?"
    # ),
    # "vulnerability": lambda party, opp_party: (
    #     warning_string
    #     + f"Can you suggest a rephrasing of that message, where the {party} instead "
    #     "emphasizes self-disclosure, ",
    #     "personal stories, humor, and social trust as a way to improve their conversation "
    #     "with the {opp_party} and decision-making? The idea is that vulnerability increases "
    #     "trust and understanding among others, which seems crucial when having "
    #     "disagreements and discussions.",
    # ),
    # "translate_values": lambda party, opp_party: (
    #     warning_string
    #     + f"Can you suggest a rephrasing of that message, where the {party} "
    #     "still communicates their position, but motivates it with different "
    #     "underlying concerns? It also doesn't necessarily have to emphasize that "
    #     "we all believe the same thing."
    # ),
    # "perspective_taking": lambda party, opp_party: (
    #     warning_string
    #     + f"Can you suggest a rephrasing of that message, where the {party} instead "
    #     f"expresses what they think it would be like to be in {opp_party}'s "
    #     "position, and then reaffirm the original message?"
    # ),
    # "perspective_getting": lambda party, opp_party: (
    #     warning_string
    #     + f"Can you suggest a rephrasing of that message, where the {party} instead "
    #     f"actively requests the view of {opp_party} in a non-judgmental and "
    #     "listening way?"
    # ),
}

INSTRUCTIONS = "Read this conversation between two people who disagree about gun control laws in the United States:"


EXEMPLAR_RUNNING_CONVO = [
    "Opponent: I think the current gun control laws do not need any further regulation as it will only restrict the rights of law abiding citizens and leave them more vulnerable to criminals that avert gun control laws anyway. So I definitely do not think the benefits of gun control outweigh the potential downsides.",
    "Supporter: I think there should be stricter background checks, not only the mentally ill but also people with misdemeanor charges, especially if it is some sort of violence; and longer wait times. There also need to be background checks at gun shows. I believe all guns need to be registered.",
    "Opponent: Gun ownership already requires registration of the firearm(s), FYI.",
]


PROMPT = '''"""
{instructions}

{exemplar_running_convo}

Now the opponent wants to say: '{exemplar_message}'

{exemplar_rephrasing_spec}

Here is the suggested rephrasing:
"{exemplar_rephrasing}"
"""

"""
{instructions}

{running_convo}

Now the {position} wants to say: '{message}'

{rephrasing_spec}

Here is the suggested rephrasing:
"'''


if OPENAPI_API_KEY := os.getenv("OPENAI_API_KEY"):
    openai.api_key = OPENAPI_API_KEY
else:
    with open("OPENAI_API_KEY.txt", "r") as f:
        openai.api_key = f.read().strip()


def create_running_convo(turns):
    return "\n".join(f'{turn["position"]}: {turn["message"].strip()}' for turn in turns)


def create_prompt(turns, spec):
    if len(turns) < 2:
        raise ValueError("Not enough turns to create a prompt (must be >= 2)")

    turn_row = turns[-1]
    position = turn_row["position"]
    opp_position = REVERSE_POSITION_MAP[turn_row["position"]]
    message = turn_row["message"]
    opponent_message = re.search("(?<=Opponent: ).*", EXEMPLAR_RUNNING_CONVO[-1]).group(
        0
    )
    exemplar_rephrasing = (
        "I understand that you would feel safer if all guns in the United "
        "States were registered. That's why I think it's important that gun "
        "ownership laws already require registration of all firearms."
    )
    return PROMPT.format(
        instructions=INSTRUCTIONS,
        exemplar_running_convo="\n".join(EXEMPLAR_RUNNING_CONVO[:-1]),
        exemplar_message=opponent_message,
        exemplar_rephrasing_spec=spec("Opponent", "Supporter"),
        exemplar_rephrasing=exemplar_rephrasing,
        running_convo=create_running_convo(turns[:-1]),
        position=position.lower(),
        message=message,
        rephrasing_spec=spec(position, opp_position),
    )


def rephrasings_generator(prompt, n=1, request_logprobs=False):
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=prompt,
        max_tokens=100,
        temperature=0.7,
        stream=True,
        n=n,
        logprobs=3 if request_logprobs else None,
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


def create_rephrasing_for_turns(turns, spec, *, n=1, request_logprobs=False):
    prompt = create_prompt(turns, spec)
    return rephrasings_generator(prompt, n, request_logprobs)


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
