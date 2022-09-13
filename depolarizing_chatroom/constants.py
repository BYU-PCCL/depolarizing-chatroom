import os

MIN_COUNTED_MESSAGE_WORD_COUNT = 4
MIN_REPHRASING_TURNS = 2
REPHRASE_EVERY_N_TURNS = 2
REQUIRED_REPHRASINGS = 5
SOCKET_NAMESPACE_CHATROOM = "/chatroom"
SOCKET_NAMESPACE_WAITING_ROOM = "/waiting-room"
POST_SURVEY_URL = (
    f'{os.environ["POST_SURVEY_URL"]}?LinkID={{link_id}}&treatment={{treatment}}'
    if "POST_SURVEY_URL" in os.environ
    else None
)
