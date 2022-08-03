# build incoming-nordic
FROM python:3.10.4 as incoming-nordic

# set app directory
WORKDIR /usr/src/app

# install dependencies
COPY ./requirements.txt .
RUN pip install -r requirements.txt
RUN pip install gunicorn

# install application
COPY ./*.py .
COPY ./core/ ./core/
COPY ./incoming-nordic/ .

# expose the default HTTPS port
EXPOSE 80

# run tests
RUN [ "python", "run.py", "test" ]

# healthcheck
HEALTHCHECK --interval=20s --timeout=30s --retries=12 --start-period=1200s \
            CMD http_proxy="" https_proxy="" curl --fail \
            http://${HOST-0.0.0.0}:${PORT:-80}/incoming-nordic/v1/health/ || exit 1

# run the application
CMD gunicorn run:app \
    --log-level=${GUNICORN_LOGLEVEL:-info} --access-logfile - \
    --bind 0.0.0.0:${PORT:-80} \
    --worker-class=${GUNICORN_WORKER_CLASS:-gthread} \
    --workers ${GUNICORN_WORKERS:-1} \
    --threads ${GUNICORN_THREADS:-4}
