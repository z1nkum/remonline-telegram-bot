FROM python:3.7-alpine3.8
RUN apk update && apk add --virtual build-dependencies build-base gcc wget git libffi-dev
RUN apk add --virtual build-dependencies openssl-dev
ADD requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
WORKDIR /app
ADD bot.py /app/bot.py
# You should specify bellow env variables to run
#ENV TG_TOKEN 123123123
#ENV TG_CHAT_IDS 123123,-123
#ENV API_KEY 123123123
ENV DEBUG False
CMD [ "python", "./bot.py" ]