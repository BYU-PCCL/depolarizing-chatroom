import logging

logger = logging.getLogger("depolarizing_chatroom")

# I really don't want to do this but I can't figure out what the "right" way to
# configure a specific logger's level at runtime is. Why is Python's logging module so
# opaque?
# Set log level to debug
logger.setLevel(logging.DEBUG)

# Create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create formatter
# formatter = logging.Formatter(
#     "%(asctime)s [%(process)d] [%(levelname)s] [%(name)s] %(message)s",
#     "[%Y-%m-%d %H:%M:%S %z]",
# )
#
# # Add formatter to ch
# ch.setFormatter(formatter)
#
# Add ch to logger
# logger.addHandler(ch)


def format_parameterized_log_message(message: str, **kwargs) -> str:
    params_items = [f"{k}={repr(v)}" for k, v in kwargs.items()]
    params_str = f' [{", ".join(params_items)}]' if kwargs else ""
    return f"{message}{params_str}"
