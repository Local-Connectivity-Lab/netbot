FROM python:3.11

LABEL maintainer="Paul Philion <philion@acmerocket.com>"

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

COPY ./*.py /
RUN chmod +x /netbot.py

ENV PYTHONPATH=/

# start the bot
CMD ["/netbot.py"]