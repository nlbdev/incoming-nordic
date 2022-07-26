#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import sys

import pybrake

import cache
import server

if sys.version_info[0] != 3 or sys.version_info[1] < 7:
    print("# This script requires Python version 3.7+")
    sys.exit(1)


# Avoid sending lots of exceptions like "The read operation timed out" to pybrake.io
class PybrakeLoggingFilter(logging.Filter):
    def filter(self, record):
        return "pybrake" not in record.getMessage()


debug = "debug" in sys.argv or os.environ.get("DEBUG", "1") == "1"
log_level = logging.DEBUG if debug else logging.INFO
logging.getLogger().setLevel(log_level)
logging.basicConfig(stream=sys.stdout,
                    level=log_level,
                    format="%(asctime)s %(levelname)-8s %(message)s")

app = server.app
airbrake_config = {
    "project_id": os.getenv("AIRBRAKE_PROJECT_ID", None),
    "project_key": os.getenv("AIRBRAKE_PROJECT_KEY", None),
    "environment": os.getenv("AIRBRAKE_ENVIRONMENT", "development")
}

if server.test:
    cache.cacheReady = True

else:
    # add airbrake.io handler
    if airbrake_config["project_id"] is not None and airbrake_config["project_key"] is not None:
        notifier = pybrake.Notifier(**airbrake_config)
        airbrake_handler = pybrake.LoggingHandler(notifier=notifier, level=logging.ERROR)
        airbrake_handler.addFilter(PybrakeLoggingFilter)
        logging.getLogger().addHandler(airbrake_handler)

        app.config['PYBRAKE'] = airbrake_config
        app = pybrake.middleware.flask.init_app(app)

    else:
        airbrake_config = None
        logging.warn("Airbrake.io not configured (missing AIRBRAKE_PROJECT_ID and/or AIRBRAKE_PROJECT_KEY)")

    cache.start()


# gunicorn will invoke `app` here. See Dockerfile.
gunicorn_logger = logging.getLogger('gunicorn.error')
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)
