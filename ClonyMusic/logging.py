import logging

_err_handler = logging.FileHandler("error.txt", encoding="utf-8")
_err_handler.setLevel(logging.ERROR)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler("log.txt", encoding="utf-8"),
        _err_handler,
        logging.StreamHandler(),
    ],
)

for noisy in [
    "httpx",
    "pyrogram",
    "pytgcalls",
    "aiohttp",
    "asyncio",
    "urllib3",
    "motor",
    "pymongo",
    "git",
    "PIL",
]:
    logging.getLogger(noisy).setLevel(logging.ERROR)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
