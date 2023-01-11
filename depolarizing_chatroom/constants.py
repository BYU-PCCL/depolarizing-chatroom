import os

MIN_COUNTED_MESSAGE_WORD_COUNT = 3
MIN_REPHRASING_TURNS = 2
REPHRASE_EVERY_N_TURNS = 2
REQUIRED_REPHRASINGS = 4
MAX_REPHRASING_ATTEMPTS = 10
SOCKET_NAMESPACE_CHATROOM = "/chatroom"
SOCKET_NAMESPACE_WAITING_ROOM = "/waiting-room"
WAITING_ROOM_TIMEOUT = 5 * 60  # 5 minutes
POST_CHAT_URL = (
    f'{os.environ["POST_CHAT_URL"]}?RESPONDENT_ID={{respondent_id}}&treatment={{treatment}}&position={{position}}'
    if "POST_CHAT_URL" in os.environ
    else None
)
NO_CHAT_URL = (
    f'{os.environ["NO_CHAT_URL"]}?RESPONDENT_ID={{respondent_id}}&position={{position}}'
    if "NO_CHAT_URL" in os.environ
    else None
)
