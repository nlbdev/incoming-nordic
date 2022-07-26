# Dockerfile for the daisy202-to-distribution process
FROM python:3.10.4

# Create app directory
WORKDIR /usr/src/app

# Install dependencies
COPY ./requirements.txt .
RUN pip install -r requirements.txt
RUN pip install gunicorn

# Install application
COPY ./*.py .
COPY ./daisy202-to-distribution/ .

# expose the default HTTPS port
EXPOSE 80

# Run tests
RUN [ "python", "run.py", "test" ]

HEALTHCHECK --interval=20s --timeout=30s --retries=12 --start-period=1200s \
            CMD http_proxy="" https_proxy="" curl --fail \
            http://${HOST-0.0.0.0}:${PORT:-80}/daisy202-to-distribution/v1/health/ || exit 1

CMD gunicorn run:app \
    --log-level=${GUNICORN_LOGLEVEL:-info} --access-logfile - \
    --bind 0.0.0.0:${PORT:-80} \
    --worker-class=${GUNICORN_WORKER_CLASS:-gthread} \
    --workers ${GUNICORN_WORKERS:-1} \
    --threads ${GUNICORN_THREADS:-4}
