from dialog_bot_sdk.bot import DialogBot
from dialog_bot_sdk import interactive_media
import grpc
import os
import sqlite3
import json
import time
import datetime
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import xlwt


class Bot:
    def __init__(self):
        load_dotenv('.env')
        self.con = sqlite3.connect('db.db', check_same_thread=False)
        self.bot = DialogBot.get_secure_bot(
            os.environ.get('BOT_ENDPOINT'),
            grpc.ssl_channel_credentials(),
            os.environ.get('BOT_TOKEN')
        )
        self.header_style = xlwt.easyxf(
            'pattern: pattern solid, fore_colour light_yellow;'
            'font: bold True;'
            'borders: top_color black, bottom_color black, right_color black, left_color black,'
            'left thin, right thin, top thin, bottom thin;'
        )
        self.bot.messaging.on_message_async(self.on_msg, self.on_click)

    def on_msg(self, *params):
        user = self.get_user(params[0].sender_uid)
        message = str(params[0].message.textMessage.text)
        if user:
            state = user[3]
        else:
            self.create_user(params[0].sender_uid)
            state = 'menu'

        if message == '/start':
            self.set_state(user[0], 'menu')
            self.bot.messaging.send_message(
                params[0].peer,
                '\U0001F44B Привет!\n'
                'Я — бот для удобного подсчета трат.',
                [
                    interactive_media.InteractiveMediaGroup(
                        [

                            interactive_media.InteractiveMedia(
                                1,
                                interactive_media.InteractiveMediaButton('add', 'Добавить расходы'),
                                'primary'
                            ),
                            interactive_media.InteractiveMedia(
                                2,
                                interactive_media.InteractiveMediaButton('reset', 'Изменить бюджет'),
                                'primary'
                            ),
                            interactive_media.InteractiveMedia(
                                3,
                                interactive_media.InteractiveMediaButton('view_spending', 'Посмотреть расходы'),
                                'primary'
                            ),
                            interactive_media.InteractiveMedia(
                                4,
                                interactive_media.InteractiveMediaButton('export', 'Экспортировать расходы в Excel'),
                                'primary'
                            ),
                            interactive_media.InteractiveMedia(
                                5,
                                interactive_media.InteractiveMediaButton('reset_spending', 'Обнулить траты'),
                                'danger'
                            )
                        ]
                    )
                ]
            )
        elif state == 'reset':
            try:
                budget = abs(float(message.strip()))
                self.set_budget(budget)
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    '\U0001F44C Готово.'
                )
                self.set_state(user[0], 'menu')
            except ValueError:
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    'Кажется, это не число.\nМне нужно что-то такое: 1234.56'
                )
        elif state == 'menu':
            try:
                val = float(message.strip())
                state_info = json.dumps({'val': val})
                self.set_state_info(user[0], state_info)
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    'Пришли короткое описание траты.',
                    [
                        interactive_media.InteractiveMediaGroup(
                            [

                                interactive_media.InteractiveMedia(
                                    1,
                                    interactive_media.InteractiveMediaButton('no_descr', 'Оставить без описания')
                                )
                            ]
                        )
                    ]
                )
                self.set_state(user[0], 'add_descr')
            except ValueError:
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    'Кажется, это не число \U0001F914'
                )
        elif state == 'add_descr':
            state_info = json.loads(user[4])
            self.spend_action(user, float(state_info['val']), message.strip())
            self.set_state_info(user[0], '')
            self.set_state(user[0], 'menu')
        elif state == 'reset_spending':
            try:
                n = int(message.strip())
                self.reset_spending(n)
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    'Трата под номером *%s* удалена.' % n
                )
                self.set_state(user[0], 'menu')
            except ValueError:
                self.bot.messaging.send_message(
                    self.bot.users.get_user_peer_by_id(user[0]),
                    'Это не номер траты.'
                )

    def on_click(self, *params):
        user = self.get_user(params[0].uid)
        value = params[0].value
        if value == 'add':
            self.set_state(user[0], 'menu')
            self.bot.messaging.send_message(
                self.bot.users.get_user_peer_by_id(user[0]),
                'Ты можешь присылать мне любые суммы.\nКаждая будет автоматически добавляться в расходы.'
            )
        elif value == 'reset':
            self.set_state(user[0], 'reset')
            self.bot.messaging.send_message(
                self.bot.users.get_user_peer_by_id(user[0]),
                'Ок, пришли мне новый размер бюджета.'
            )
        elif value == 'reset_spending':
            self.set_state(user[0], 'reset_spending')
            self.bot.messaging.send_message(
                self.bot.users.get_user_peer_by_id(user[0]),
                'Пришли мне номер траты для удаления.\n'
                'Также можешь удалить *все* расходы, нажав на кнопку',
                [
                    interactive_media.InteractiveMediaGroup(
                        [

                            interactive_media.InteractiveMedia(
                                7,
                                interactive_media.InteractiveMediaButton('reset_all', 'Удалить все'),
                                'danger'
                            )
                        ]
                    )
                ]
            )
        elif value == 'reset_all':
            self.reset_spending()
            self.bot.messaging.send_message(
                self.bot.users.get_user_peer_by_id(user[0]),
                '\U0001F44C Расходы обнулены.'
            )
        elif value == 'no_descr':
            state_info = json.loads(user[4])
            self.spend_action(user, float(state_info['val']))
            self.set_state_info(user[0], '')
            self.set_state(user[0], 'menu')
        elif value == 'view_spending':
            data = self.view_spending()
            budget, spending = self.get_info()
            self.bot.messaging.send_message(
                self.bot.users.get_user_peer_by_id(user[0]),
                '*Список расходов*\n\n'
                '%s\n\n'
                'Итого трат: *%s*, остаток: *%s*' % ('\n'.join([str(int(data[i][0]) + 1) + '. *' + str(data[i][2]) +
                                                                ':* ' + str(data[i][1]) + ' (' +
                                                                str(datetime.datetime.fromtimestamp(data[i][3])
                                                                    .strftime('%d.%m.%Y %H:%M'))
                                                                + ')'
                                                                if data[i][2] != ''
                                                                else str(int(data[i][0]) + 1) + '. *Без описания:* ' +
                                                                     str(data[i][1]) + ' (' +
                                                                str(datetime.datetime.fromtimestamp(data[i][3])
                                                                    .strftime('%d.%m.%Y %H:%M'))
                                                                + ')'
                                                                for i in range(len(data))]),
                                                     spending,
                                                     budget - spending),
                [
                    interactive_media.InteractiveMediaGroup(
                        [

                            interactive_media.InteractiveMedia(
                                1,
                                interactive_media.InteractiveMediaButton('add', 'Добавить расходы'),
                                'primary'
                            ),
                            interactive_media.InteractiveMedia(
                                2,
                                interactive_media.InteractiveMediaButton('reset', 'Изменить бюджет'),
                                'primary'
                            ),
                            interactive_media.InteractiveMedia(
                                3,
                                interactive_media.InteractiveMediaButton('view_spending', 'Посмотреть расходы'),
                                'primary'
                            ),
                            interactive_media.InteractiveMedia(
                                4,
                                interactive_media.InteractiveMediaButton('export', 'Экспортировать расходы в Excel'),
                                'primary'
                            ),
                            interactive_media.InteractiveMedia(
                                5,
                                interactive_media.InteractiveMediaButton('reset_spending', 'Обнулить траты'),
                                'danger'
                            )
                        ]
                    )
                ]
            )
        elif value == 'export':
            path = self.export_to_excel()
            self.bot.messaging.send_file(self.bot.users.get_user_peer_by_id(user[0]), path)
            os.remove(path)

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

    def set_budget(self, budget):
        cur = self.con.cursor()
        cur.execute('UPDATE settings SET val = ? WHERE name = "budget"', (float(budget),))
        self.con.commit()
        cur.close()
        return True

    def reset_spending(self, n=None):
        cur = self.con.cursor()
        if not n:
            cur.execute('DELETE FROM spending')
        else:
            cur.execute('DELETE FROM spending WHERE id = ?', (int(n) - 1, ))
        self.con.commit()
        cur.close()
        return True

    def view_spending(self):
        cur = self.con.cursor()
        data = cur.execute('SELECT * FROM spending').fetchall()
        self.con.commit()
        cur.close()
        return data

    def spend(self, val, descr):
        cur = self.con.cursor()
        cur.execute('INSERT INTO spending (val, descr, time) VALUES (?, ?, ?)', (float(val), str(descr),
                                                                                 int(time.time())))
        self.con.commit()
        budget = float(cur.execute('SELECT * FROM settings').fetchone()[1])
        spending = float(cur.execute('SELECT SUM(val) FROM spending').fetchone()[0])
        cur.close()
        deg = (100 - spending / (budget / 100)) * 3.6
        img = Image.new('RGBA', (180, 210), (0, 0, 0, 0))
        x = 90
        y = 120
        r1 = 85
        r2 = 55
        draw = ImageDraw.Draw(img)
        draw.ellipse((x - r1, y - r1, x + r1, y + r1), fill=(231, 76, 60))
        draw.ellipse((x - r2, y - r2, x + r2, y + r2), fill=(0, 0, 0, 0))
        draw.arc((x - r1, y - r1, x + r1, y + r1), 270, 270 + deg, width=30, fill=(89, 109, 131))
        unicode_font = ImageFont.truetype('DejaVuSans.ttf', 14)
        unicode_font_b = ImageFont.truetype('DejaVuSans.ttf', 30)
        msg = 'осталось'
        w, h = draw.textsize(msg, font=unicode_font)
        balance = str(round(100 - spending / (budget / 100), 1)) + '%'
        w_b, h_b = draw.textsize(balance, font=unicode_font_b)
        draw.text(((x * 2 - w) // 2, 8), msg, font=unicode_font, fill=(0, 0, 0))
        draw.text(((x * 2 - w_b) // 2, 90 + h_b // 2), balance, font=unicode_font_b, fill=(0, 0, 0))
        path = 'budget.png'
        img.save(path, 'PNG')
        balance = budget - spending
        return [balance, path]

    def get_info(self):
        cur = self.con.cursor()
        budget = float(cur.execute('SELECT * FROM settings').fetchone()[1])
        try:
            spending = float(cur.execute('SELECT SUM(val) FROM spending').fetchone()[0])
        except TypeError:
            spending = 0.0
        cur.close()
        return [budget, spending]

    def spend_action(self, user, val, descr=''):
        balance, path = self.spend(val, descr)
        self.bot.messaging.send_message(
            self.bot.users.get_user_peer_by_id(user[0]),
            'Остаток: *%s*' % balance,
            [
                interactive_media.InteractiveMediaGroup(
                    [

                        interactive_media.InteractiveMedia(
                            1,
                            interactive_media.InteractiveMediaButton('add', 'Добавить расходы'),
                            'primary'
                        ),
                        interactive_media.InteractiveMedia(
                            2,
                            interactive_media.InteractiveMediaButton('reset', 'Изменить бюджет'),
                            'primary'
                        ),
                        interactive_media.InteractiveMedia(
                            3,
                            interactive_media.InteractiveMediaButton('view_spending', 'Посмотреть расходы'),
                            'primary'
                        ),
                        interactive_media.InteractiveMedia(
                            4,
                            interactive_media.InteractiveMediaButton('export', 'Экспортировать расходы в Excel'),
                            'primary'
                        ),
                        interactive_media.InteractiveMedia(
                            5,
                            interactive_media.InteractiveMediaButton('reset_spending', 'Обнулить траты'),
                            'danger'
                        )
                    ]
                )
            ]
        )
        self.bot.messaging.send_image(self.bot.users.get_user_peer_by_id(user[0]), path)
        os.remove(path)

    def export_to_excel(self):
        book = xlwt.Workbook()
        sheet = book.add_sheet('Лист1', cell_overwrite_ok=True)
        sheet.write(0, 0, 'Сумма', self.header_style)
        sheet.write(0, 1, 'Описание', self.header_style)
        sheet.write(0, 2, 'Дата', self.header_style)

        data = self.view_spending()
        print(data)
        sheet.col(0).width = 256 * 10
        sheet.col(1).width = 256 * 15
        sheet.col(2).width = 256 * 15
        for i in range(len(data)):
            sheet.write(i + 1, 0, data[i][1])
            sheet.write(i + 1, 1, data[i][2])
            sheet.write(i + 1, 2, str(datetime.datetime.fromtimestamp(data[i][3])
                                                                    .strftime('%d.%m.%Y %H:%M')))

        filename = 'Расходы.xls'
        book.save(filename)
        return filename


bot = Bot()
