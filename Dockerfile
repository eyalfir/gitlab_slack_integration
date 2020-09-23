FROM python:3.8.5

RUN mkdir /app
RUN pip install Flask==1.0.2 redis==3.2.0 gunicorn==19.9.0 requests==2.23.0
ENV WORKERS=8
ENV PORT=8000
COPY gitlab_app.py /app
WORKDIR /app
CMD ["/bin/bash", "-c", "gunicorn --bind 0.0.0.0:${PORT} -w ${WORKERS} gitlab_app:app"]
