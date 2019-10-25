from dialog_bot_sdk.bot import DialogBot
from dialog_bot_sdk import interactive_media
import grpc
import os
import sqlite3
from dotenv import load_dotenv
import json
import datetime


class Bot:
    def __init__(self):
        load_dotenv('.env')
        self.con = sqlite3.connect('db.db', check_same_thread=False)
        self.bot = DialogBot.get_secure_bot(
            os.environ.get('BOT_ENDPOINT'),
            grpc.ssl_channel_credentials(),
            os.environ.get('BOT_TOKEN')
        )
        self.bad = []
        self.bot.messaging.on_message_async(self.on_msg, self.on_click)

    def on_msg(self, *params):
        user = self.get_user(params[0].sender_uid)
        message = str(params[0].message.textMessage.text)
        if user:
            state = user[3]
        else:
            self.create_user(params[0].sender_uid)
            state = 'menu'

        if user[2] == 'admin':
            if message == '/start':
                self.set_state(user[0], 'menu')
                self.bot.messaging.send_message(
                    params[0].peer,
                    '\U0001F44B Привет!\n'
                    'Я — бот.'
                )

    def get_user(self, uid):
        cur = self.con.cursor()
        user = cur.execute('SELECT * FROM users WHERE id = ? LIMIT 1', (int(uid),)).fetchone()
        if not user:
            username = str(self.bot.users.get_user_by_id(uid).data.nick.value)
            self.create_user(uid, username=username, role='user')
            self.con.commit()
            user = cur.execute('SELECT * FROM users WHERE id = ? LIMIT 1', (int(uid),)).fetchone()
        cur.close()
        return user if user else None

    def create_user(self, uid, username='', role='user'):
        cur = self.con.cursor()
        user = cur.execute('INSERT INTO users(id, username, role, state, state_info) VALUES (?, ?, ?, "menu", "");',
                           (int(uid), str(username), str(role))).fetchone()
        cur.close()
        return user if user else None

    def set_state(self, uid, state):
        cur = self.con.cursor()
        cur.execute('UPDATE users SET state = ? WHERE id = ?', (str(state), int(uid)))
        self.con.commit()
        cur.close()
        return True

    def set_state_info(self, uid, state_info):
        cur = self.con.cursor()
        cur.execute('UPDATE users SET state_info = ? WHERE id = ?', (str(state_info).replace("'", '"'), int(uid)))
        self.con.commit()
        cur.close()
        return True

    def back_to_menu(self, user):
        self.bot.messaging.send_message(
            self.bot.users.get_user_peer_by_id(user[0]),
            'Главное меню',
            [
                interactive_media.InteractiveMediaGroup(
                    [
                        interactive_media.InteractiveMedia(
                            1,
                            interactive_media.InteractiveMediaButton('add_event', 'Добавить мероприятие'),
                            'primary'
                        ),
                        interactive_media.InteractiveMedia(
                            2,
                            interactive_media.InteractiveMediaButton('view_events',
                                                                     'Посмотреть мероприятия'),
                            'primary'
                        )
                    ]
                )
            ]
        )
        self.set_state(user[0], 'menu')
        self.set_state_info(user[0], '')


bot = Bot()
