FROM python:3.11

LABEL maintainer="Paul Philion <philion@acmerocket.com>"

RUN pip install --no-cache-dir -r requirements.txt

COPY ./netbot.py /netbot.py
RUN chmod +x /netbot.py

ENV PYTHONPATH=/

# start the bot
CMD ["/netbox.py"]