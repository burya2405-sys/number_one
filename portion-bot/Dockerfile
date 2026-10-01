FROM python:3.12-slim
WORKDIR /app
COPY bot.py nutrition.py storage.py vision.py ./
RUN useradd --create-home bot && mkdir data && chown bot:bot data
USER bot
VOLUME ["/app/data"]
CMD ["python", "-u", "bot.py"]
