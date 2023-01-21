# NOTE: the chatroom also requires:
# - OPENAI_API_KEY
# - NO_CHAT_URL
# - POST_CHAT_URL
# These are provided in run-all.sh. Ask @vinhowe if you need help with these.
source ./venv/bin/activate
TEMPLATES_DIR=./templates \
PYTHONUNBUFFERED=TRUE \
python3 -mgunicorn \
--bind 0.0.0.0:$1 \
--worker-class uvicorn.workers.UvicornWorker \
--log-config gunicorn-log-config.conf \
-w 1 \
depolarizing_chatroom.server:app
