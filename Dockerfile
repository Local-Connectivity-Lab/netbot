FROM python:3.11

LABEL maintainer="Paul Philion <philion@acmerocket.com>"

RUN pip install --no-cache-dir -r requirements.txt

COPY ./netbox.py /netbox.py
RUN chmod +x /netbox.py

ENV PYTHONPATH=/

# start the bot
CMD ["/netbox.py"]