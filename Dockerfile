FROM python:3.13

WORKDIR /usr/src/app

# install the code
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# start the bot
CMD ["python", "-m", "netbot.netbot"]