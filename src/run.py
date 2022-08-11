#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import sys

import core.endpoints.health
import endpoints.routes
import server

if sys.version_info[0] != 3 or sys.version_info[1] < 7:
    print("# This script requires Python version 3.7+")
    sys.exit(1)


debug = "debug" in sys.argv or os.environ.get("DEBUG", "1") == "1"
log_level = logging.DEBUG if debug else logging.INFO
logging.getLogger().setLevel(log_level)
logging.basicConfig(stream=sys.stdout,
                    level=log_level,
                    format="%(asctime)s %(levelname)-8s %(message)s")

app = server.app

# gunicorn will invoke `app` here. See Dockerfile.
gunicorn_logger = logging.getLogger('gunicorn.error')
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)
