# remonline-telegram-bot

Telegram bot for remonline.ru

### Telegram API access notice

The bot needs a direct connection to the Telegram API servers (surprise!), and recently in some countries it does not work very well. Therefore, we recommend installing the bot on hosting outside these countries

### Getting starting

At first you need to [create your own Telegram bot](https://core.telegram.org/bots#3-how-do-i-create-a-bot)

As a result you'll obtain your authorization token for bot. It's your TG_TOKEN (see bellow)

Find your bot and start chat with him. You will need it to test he is working well

Then you need to obtain API_KEY from [remonline.ru site](https://app.remonline.ru/#!/settings/api)

Then clone this repo: `git clone https://github.com/z1nkum/remonline-telegram-bot.git`

You can run bot at this point with some python virtual environments magic, but we suggest you to use docker for that

### Docker Compose

Install docker/docker compose

Copy .env.sample to .env and place it near the docker-compose.yaml

Edit .env file and place TG_TOKEN and API_KEY. 

Run bot with `docker-compose up` and send `/chat_id` command to chat with bot included. 

You'll get chat id (negative for group chats, and positive for direct)

Place it as a value to TG_CHAT_IDS (and TG_CHAT_NOTICE_IDS if needed)

You can add more than one chat_id there: use commas to separate them in this case


### Environment variables

Place following variables to .env file near the docker-compose.yaml

| ENV name      | Required           | Description  |
| ------------- |:-------------:| -----:|
| TG_TOKEN      | yes | Your's bot telegram token. Ask @BotFather for it  |
| TG_CHAT_IDS   | yes | Only this chats/contacts will be able to interact with bot. Comma-separated list |
| TG_CHAT_NOTICE_IDS   | no | Only this chats/contacts will be noticed about polled events. Comma-separated list |
| API_KEY       | yes | API key obtained from remonline.ru (settings/api) | 
| DEBUG         | no  | Verbosity output. True or False (default) | 


### Supported commands

| Command      | Restricted           | Description  |
| ------------- |:-------------:| -----:|
| /get_orders, /go  | yes | Get list of orders or details about exact order (if order label passed)  |
| /clients, /cl   | yes | Get list of clients |
| /chat_id   | no | Get current chat id. Use it to define TG_CHAT_IDS and/or TG_CHAT_NOTICE_IDS|
| /statuses       | yes | Get list of possible order statuses | 


### Permanent Docker Compose via systemd

```bash
mkdir -p /etc/docker/compose/remonline
cp docker-compose.yaml /etc/docker/compose/remonline/
cp .env /etc/docker/compose/remonline/
```

/etc/systemd/system/docker-compose@.service

```
[Unit]
Description=%i service with docker compose
Requires=docker.service
After=docker.service

[Service]
Restart=always

WorkingDirectory=/etc/docker/compose/%i

# Remove old containers, images and volumes. Always pull new image
ExecStartPre=/bin/docker-compose down -v
ExecStartPre=/bin/docker-compose rm -fv
ExecStartPre=/bin/docker-compose pull
ExecStartPre=-/bin/bash -c 'docker volume ls -qf "name=%i_" | xargs docker volume rm'
ExecStartPre=-/bin/bash -c 'docker network ls -qf "name=%i_" | xargs docker network rm'
ExecStartPre=-/bin/bash -c 'docker ps -aqf "name=%i_*" | xargs docker rm'

# Compose up
ExecStart=/bin/docker-compose up

# Compose down, remove containers and volumes
ExecStop=/bin/docker-compose down -v

[Install]
WantedBy=multi-user.target
```

Enable and start service

```
systemctl enable docker-compose@remonline.service
systemctl start docker-compose@remonline.service
```


### Related links

GitHub: https://github.com/z1nkum/remonline-telegram-bot

Docker Hub: https://hub.docker.com/r/z1nkum/remonline-telegram-bot/
