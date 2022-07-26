import copy
import logging
import os
import pickle
import re
import sys
import threading
import time

from read_write_lock import ReadWriteLock

refresher_thread = None
shouldRun = False
cacheReady = False
autorefreshers_initialized = []
test = "test" in sys.argv or os.environ.get("TEST", "0") == "1"
cache = {}
cache_refresher_functions = []
lock = ReadWriteLock()

CACHE_REFRESH_INTERVAL = int(os.getenv("CACHE_REFRESH_INTERVAL", default=60*1))


def start():
    global lock
    global cache
    global refresher_thread
    global shouldRun

    shouldRun = True

    refresher_thread = threading.Thread(target=cache_refresher_thread, name="cache refresher")
    refresher_thread.setDaemon(True)
    refresher_thread.start()


def cache_refresher_thread():
    global shouldRun
    global cacheReady
    global cache_refresher_functions
    global autorefreshers_initialized
    global CACHE_REFRESH_INTERVAL

    last_refresh = 0
    while shouldRun:
        try:
            current_time = time.time()

            if current_time - last_refresh < CACHE_REFRESH_INTERVAL:
                time.sleep(abs(CACHE_REFRESH_INTERVAL + last_refresh - current_time))

            for func in cache_refresher_functions:
                func()

                if f"autorefresher@{func.__name__}" not in autorefreshers_initialized:
                    autorefreshers_initialized.append(f"autorefresher@{func.__name__}")

            last_refresh = time.time()

            # after the first cache iteration, flag the cache as ready
            cacheReady = True

        except Exception as e:
            logging.exception(f"An error occured while updating the cache: {str(e) if str(e) else '(unknown)'}")

        finally:
            time.sleep(10)


def autorefresher(func):
    global cache_refresher_functions
    global autorefreshers_initialized
    global test

    if test:  # don't mark as "done caching" while testing
        autorefreshers_initialized.append(f"autorefresher@{func.__name__}")

    if func not in cache_refresher_functions:
        cache_refresher_functions.append(func)

    return func


def store(cache_id, result):
    global lock
    global cache

    with lock.write():
        cache[cache_id] = copy.deepcopy(result)
        logging.debug(f"stored in cache: {cache_id}")


def is_cached(cache_id):
    global lock
    global cache

    with lock.read():
        if cache_id in cache:
            return True

        if cache_id in autorefreshers_initialized:
            return True

    return False


def get(cache_id, filter_function=None, filter_args={}):
    global lock
    global cache

    with lock.read():
        if cache_id not in cache:
            logging.debug(f"{cache_id} is not in cache")
            return None

        else:
            logging.debug(f"getting from cache: {cache_id}")
            result = filtered_deepcopy(cache[cache_id], filter_function, filter_args, name=cache_id)
            return result


def filtered_deepcopy(data, filter_function=None, filter_args={}, name=None):
    before_deepcopy = time.time()
    if filter_function is not None:
        data = filter_function(data, **filter_args)
    data = copy.deepcopy(data)
    logging.debug(f"deepcopy time was {int((time.time() - before_deepcopy)*1000)}{' for ' + str(len(data)) + ' items in: ' + str(name) if name else ''}")
    return data


def clean():  # used for testing
    global lock, cache
    with lock.write():
        cache = {}
