import logging
import os

import psutil
from flask import jsonify

import cache
import server


@server.route(server.root_path + '/health/', require_auth=None)
def health():
    try:
        head = {}

        process = psutil.Process(os.getpid())
        memory_used = process.memory_info().rss
        head["memory_used"] = memory_used
        head["memory_used_human_readable"] = human_readable_bytes(memory_used)

        if not cache.cacheReady:
            head["message"] = "Cache is not ready yet."
            return jsonify({"head": head, "data": False}), 503
        else:
            return jsonify({"head": head, "data": True}), 200

    except Exception:
        logging.exception("/health: an exception occured")
        return jsonify({"head": {"message": "An unknown error occured."}, "data": False}), 500


def human_readable_bytes(bytes):
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024**2:
        return f"{int(bytes / 1024)} kiB"
    elif bytes < 1024**3:
        return f"{int(bytes / (1024**2))} MiB"
    elif bytes < 1024**4:
        return f"{int(bytes / (1024**3))} GiB"
    elif bytes < 1024**5:
        return f"{int(bytes / (1024**4))} TiB"
    else:
        return f"{bytes} B"
