import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Database configuration
DB_CONFIG = {
    'user': 'abubakiir7',
    'password': 'abubakiir7',
    'database': 'db',
    'host': '127.0.0.1'
}

# Bot configuration
CHANNELS = [
    ('https://t.me/downtown_cases', '@downtown_cases'),
    ('https://t.me/downtown_goyard', '@downtown_goyard'),
    ('https://t.me/downtownshop_uz', '@downtownshop_uz'),
    ('https://t.me/dts_samsung', '@dts_samsung')
]
BOT_TOKEN = '6365410542:AAE9c1KsA4hg7IJEc8eRr1wvEKvlhqPV8Ns'
CHAT_ID = '@downtown_cases'

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Establish a database connection pool."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(**DB_CONFIG)

    async def close(self):
        """Close the database connection pool."""
        await self.connect()
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def add_user(self, username, referral_code, contact):
        """Add a user to the database. If the username already exists, do nothing."""
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO users (username, referral_code, invited_count, contact) 
                VALUES ($1, $2, $3, $4) 
                ON CONFLICT (username) DO NOTHING
                ''',
                username, referral_code, 0, contact
            )

    async def update_invited_count(self, referrer_id):
        """Update the invited count for a given user."""
        await self.connect()
        async with self.pool.acquire() as conn:
            # First, get the current invited count
            current_count = await conn.fetchval(
                'SELECT invited_count FROM users WHERE id = $1',
                referrer_id
            )
            
            # You can add your logic here to check the count if needed
            # For example, you might want to do something if the count is already a certain number
            
            # If you want to update the count, you can specify your logic here.
            new_count = current_count + 1  # Incrementing by 1 as an example
            await conn.execute(
                'UPDATE users SET invited_count = $1 WHERE id = $2',
                new_count, referrer_id
            )

    async def invites(self, referrer_id, username):
        await self.connect()  # Await the connection
        async with self.pool.acquire() as conn:
            # Check if the username already exists in the invites table
            existing_invite = await conn.fetchval(
                'SELECT username FROM invites WHERE username = $1 AND referrer_id = $2',
                username, referrer_id
            )
            
            if existing_invite is not None:
                # Handle the case where the username already exists
                print(f"Invite for username '{username}' already exists.")
                return  # Or raise an exception, or do whatever is appropriate
            
            # If the username does not exist, proceed with the insert
            await conn.execute(
                '''INSERT INTO invites (username, referrer_id)
                VALUES ($1, $2)''',
                username, referrer_id
            )
            
            # After inserting, update the invited count
            await self.update_invited_count(referrer_id)

    async def add_referral(self, referrer_id, invitee_username):
        """Add a referral entry to the database."""
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO referrals (referrer_id, invitee_username) VALUES ($1, $2)',
                referrer_id, invitee_username
            )

    async def get_user_by_referral_code(self, referral_code):
        """Retrieve a user ID by referral code."""
        await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT id FROM users WHERE referral_code = $1',
                referral_code
            )

    async def get_user_by_username(self, username):
        """Retrieve a user ID and invited count by username."""
        await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT id, invited_count FROM users WHERE username = $1',
                username
            )

    async def get_invite_info(self, invite_link):
        """Retrieve the referrer ID for a given invite link."""
        await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                '''
                SELECT referrer_id 
                FROM invite_links 
                WHERE invite_link = $1
                ''',
                invite_link
            )  
        
    async def get_possible_referrer(self, invite_link):
        """Retrieve the referrer ID by invite link."""
        await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                '''
                SELECT referrer_id 
                FROM invite_links 
                WHERE invite_link = $1
                ''',
                invite_link
            )

    async def get_recent_referrer(self):
        """Retrieve the most recent invite link and its referrer from the database."""
        await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                '''
                SELECT referrer_id FROM referrals
                ORDER BY created_at DESC LIMIT 1
                '''
            )
    
    async def get_user_rank_context(self, target_username):
        """Retrieve users ranked above and below a specific user, including the target user."""
        await self.connect()
        async with self.pool.acquire() as conn:
            # Fetch the rank and details of the target user
            target_user = await conn.fetchrow(
                '''
                WITH RankedUsers AS (
                    SELECT id, username, invited_count AS points,
                        ROW_NUMBER() OVER (ORDER BY invited_count DESC) AS rank
                    FROM users
                )
                SELECT id, username, points, rank
                FROM RankedUsers
                WHERE username = $1  -- The specific user to check
                ''',
                target_username  # Pass the target username as a parameter
            )

            # Check if the target user exists
            if target_user is None:
                print(f"User '{target_username}' not found.")
                return []  # Return an empty list or handle as needed

            # Fetch users ranked above the target user (limit to 5)
            users_above = await conn.fetch(
                '''
                WITH RankedUsers AS (
                    SELECT id, username, invited_count AS points,
                        ROW_NUMBER() OVER (ORDER BY invited_count DESC) AS rank
                    FROM users
                )
                SELECT id, username, points, rank
                FROM RankedUsers
                WHERE rank < (SELECT rank FROM RankedUsers WHERE username = $1)  -- Users above the target
                ORDER BY rank DESC
                LIMIT 5;
                ''',
                target_username  # Use the target username for the subquery
            )

            # Fetch users ranked below the target user (limit to 5)
            users_below = await conn.fetch(
                '''
                WITH RankedUsers AS (
                    SELECT id, username, invited_count AS points,
                        ROW_NUMBER() OVER (ORDER BY invited_count DESC) AS rank
                    FROM users
                )
                SELECT id, username, points, rank
                FROM RankedUsers
                WHERE rank > (SELECT rank FROM RankedUsers WHERE username = $1)  -- Users below the target
                ORDER BY rank ASC
                LIMIT 5;
                ''',
                target_username  # Use the target username for the subquery
            )

            # Return the target user along with users above and below
            return {
                "target": target_user,
                "above": users_above,
                "below": users_below
            }

class ReferralBot:
    def __init__(self, token):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.db = Database()  # Initialize the database

    async def on_startup(self):
        await self.db.connect()

    async def on_shutdown(self):
        await self.db.close()

    def accpet_privacy_policy_keyboard(self): 
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text='Я принимаю', callback_data='accepted')
        keyboard.adjust(1)

        return keyboard.as_markup()

    def main_menu(self): 
        keyboard = ReplyKeyboardBuilder()
        for i in ['Мой реферал', 'Мои баллы', 'Мой уровень', 'Гид', 'Язык']:
            keyboard.button(text=i)
        keyboard.adjust(1, 2, 2)

        return keyboard.as_markup(resize_keyboard=True)

    async def privacy_policy_command(self, message: types.Message):
        await message.answer(text=f'''🎉 Розыгрыш с 10 призовыми местами! 🎉

Приветствуем всех наших подписчиков! Мы запускаем розыгрыш, в котором у вас есть шанс выиграть один из 10 призов!

🏆 Как участвовать?

 1. Собирайте поинты за активность в нашем канале.
 2. Первые 10 человек с наибольшим количеством поинтов к концу месяца станут победителями!

📅 Сроки розыгрыша:

 • Розыгрыш продлится 1 месяц.

💡 Как заработать поинты?

 • Приглашайте друзей в наш канал. Даже если приглашённый друг выйдет, вы всё равно продолжите накапливать свои поинты.

🔐 Важные условия:

 • Приглашённые друзья должны оставаться в канале до конца розыгрыша. Если кто-то будет выходить и заходить обратно, такие действия приведут к блокировке.
 • Любые попытки обмана также приведут к бану.

📲 Участвуйте, зарабатывайте поинты и удачи в розыгрыше!''', reply_markup=self.accpet_privacy_policy_keyboard())
    
    async def handle_privacy_acceptance(self, callback: types.CallbackQuery):
        await callback.message.answer("Благодарим вас за согласие с нашей политикой конфиденциальности. Пожалуйста, укажите свой номер телефона.", reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Поделитесь моим номером телефона", request_contact=True)]
            ],
            one_time_keyboard=True,
            resize_keyboard=True
        ))

    async def handle_contact(self, message: types.Message):
        if message.contact:
            phone_number = message.contact.phone_number
            username = message.from_user.username or str(message.from_user.id)  # Fallback if username is None
            referral_code = f'referral_{message.from_user.id}'  # Example referral code

            # Store user information, including the phone number and referral code
            await self.db.add_user(username, referral_code, phone_number)
            await message.answer(f"Спасибо! Вы успешно зарегистрированы.", reply_markup=self.main_menu())
        else:
            await message.answer("Пожалуйста, укажите свой номер телефона, нажав на кнопку.")

    async def check_sub(self, message) -> InlineKeyboardBuilder:
            c = 0
            keyboard = InlineKeyboardBuilder()
            for i in CHANNELS:
                chat_member = await self.bot.get_chat_member(i[1], message.from_user.id)
                if chat_member.status not in ['member', 'administrator', 'creator']:
                    keyboard.button(text='Subscribe', url=i[0])
                    c += 1
            keyboard.button(text='Confirm', callback_data='confirm')
            keyboard.adjust(*[1 for _ in range(len(CHANNELS) + 1)])
            return [keyboard.as_markup(), c]
    
    async def confirm(self, callback: types.CallbackQuery) -> None:
        keyboard, c = await self.check_sub(callback)
        print(c)
        if c:
            await callback.answer(
                text='Subscribe',
            )
            return
        await self.start_command(message=callback.message)
        await self.bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)


    async def start_command(self, message: types.Message):
        keyboard, c = await self.check_sub(message)
        if c:
            await message.answer(
                text='Будьте в числе первых групп, которые будут использовать нашего бота',
                reply_markup=keyboard
            )
            return
        username = message.from_user.username or str(message.from_user.id)  # Fallback if username is None
        referral_code = f'referral_{message.from_user.id}'  # Example referral code
        if not await self.db.get_user_by_username(username):
            await self.privacy_policy_command(message)
            return
        await message.answer(f'Теперь вы можете начать добывать собственные points.', reply_markup=self.main_menu())

    async def invite_command(self, message: types.Message):
        try:
            member = await self.bot.get_chat_member(CHAT_ID, self.bot.id)
            if member.status != 'administrator':
                await message.answer("The bot does not have sufficient permissions to create invite links.")
                return

            # Create the invite link and store it in the database
            link = await self.bot.create_chat_invite_link(chat_id=CHAT_ID, name=f"Invite {message.from_user.username}")
            
            # Save the referrer and the invite link in the database
            user = await self.db.get_user_by_username(message.from_user.username)
            if user:
                referrer_id = user['id']
                await self.db.add_referral(referrer_id, link.invite_link)  # Save the referrer and the invite link

            await message.answer(f'Вот ваша пригласительная ссылка: {link.invite_link}')

        except Exception as e:
            await message.answer("An error occurred while trying to create the invite link.")
            print(f"Error creating invite link: {e}")

    async def track_invite(self, update: types.ChatMemberUpdated):
        if update.new_chat_member.status == "member":  # User has joined the chat
            user = update.new_chat_member.user  # Get the user who joined

            # Check if the user already exists in the database
            existing_user = await self.db.get_user_by_username(user.username)

            # Now attempt to associate this user with a referrer by using the most recent invite link
            # Get the most recent invite link from your `referrals` table
            referrer_info = await self.db.get_recent_referrer()  # Implement this method to fetch the most recent invite link

            if referrer_info:
                referrer_id = referrer_info['referrer_id']
                await self.db.invites(referrer_id=referrer_id, username=user.username)
                print(f"User {user.username} joined via referral ID: {referrer_id}")
            else:
                print(f"User {user.username} joined without a referral.")

    async def count_my_point(self, message: types.Message):
        username = message.from_user.username or str(message.from_user.id)  # Fallback if no username

        # Fetch the user and the invited_count from the database
        user_info = await self.db.get_user_by_username(username)

        if user_info:
            invited_count = user_info['invited_count']
            await message.answer(text=f'''✨ <b>Ваши баллы</b> ✨

Привет! 

Ты на пути к победе! 

Здесь ты можешь отслеживать свои баллы и видеть, как ты приближаешься к призовым местам.

 Собирай как можно больше баллов и получи шанс выиграть крутые призы!

💼 <b>Твои текущие баллы:</b> {invited_count}

🎯 <b>Цель:</b> Войти в топ-10 и выиграть один из главных призов! 

Не забывай, что даже если наберёшь <b>больше 250</b> баллов, ты гарантированно получишь <b>купон на 50 000 сум.</b>''', parse_mode='html')
        else:
            await message.answer("Вы еще не пригласили ни одного участника или не зарегистрированы в системе.")

    async def rank(self, message: types.Message):
        username = message.from_user.username or str(message.from_user.id)

        rank_data = await self.db.get_user_rank_context(username)

        if rank_data:
            target_user = rank_data.get("target")
            users_above = rank_data.get("above", [])
            users_below = rank_data.get("below", [])

            # Construct the response message using HTML formatting
            response = []

            # Add target user information
            response.append(f"📊 <b>Ваш текущий рейтинг</b> @{self.escape_html(target_user['username'])}:")
            response.append(f" <b>• Баллы</b>: {int(target_user['points'])*5}\n <b>• Уровень</b>: {target_user['rank']}")

            # Add users above
            response.append("<b>🔝 Пользователи выше вас в рейтинге:</b>")
            if users_above:
                i = 1
                for user in users_above:
                    response.append(f"@{self.escape_html(user['username'])} - Points: {int(user['points'])*5}, Уровень: {user['rank']}")
                    i+=1
            else:
                response.append("🔺 <b>Ни один пользователь не имеет рейтинга выше вашего.</b>")

            # Add users below
            response.append("<b>Пользователи, находящиеся ниже вас в рейтинге:</b>")
            if users_below:
                i = 1
                for user in users_below:
                    response.append(f"@{self.escape_html(user['username'])} - Points: {int(user['points'])*5}, Уровень: {user['rank']}")
                    i+=1
            else:
                response.append("🔻 <b>Пользователи ниже вас в рейтинге:</b>")
            

            response.append("Продолжайте накапливать баллы и поднимайтесь в рейтинге!")

            # Join the response list into a single message
            final_response = "\n\n".join(response)

            # Send the response back to the user
            await message.answer(final_response, parse_mode="HTML")  # Use HTML for formatting
        else:
            await message.answer("Пользователь не найден или у вас нет информации о его рейтинге.")

    def escape_html(self, text):
        """Escape special characters in HTML."""
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&#x27;",
            ">": "&gt;",
            "<": "&lt;",
            " ": "&nbsp;"
        }
        return ''.join(html_escape_table.get(c, c) for c in text)
    
    async def guide(self, message: types.Message):
        await message.answer(f'''🎉 Большой розыгрыш с 10 призовыми местами! 🎉

Дорогие подписчики, мы запускаем грандиозный розыгрыш, в котором будет 10 призовых мест! У каждого есть шанс выиграть отличные призы!

🏆 Призовые места:

 1 место — купон на 3 000 000 сум и Telegram Premium
 2 место — купон на 2 000 000 сум и Telegram Premium
 3 место — купон на 1 000 000 сум и Telegram Premium
 4 место — купон на 500 000 сум и Telegram Premium
 5 место — купон на 400 000 сум и Telegram Premium
 6 место — купон на 300 000 сум и Telegram Premium
 7 место — купон на 200 000 сум и Telegram Premium
 8 место — купон на 100 000 сум и Telegram Premium
 9 место — купон на 100 000 сум и Telegram Premium
 10 место — купон на 100 000 сум и Telegram Premium

💡 Дополнительный бонус:

 Все участники, кто наберёт более 250 поинтов, автоматически получат купон на 50 000 сум, вне зависимости от призовых мест. Без проигравших — каждый получит свой бонус!


📲 Как использовать купоны?

Эти купоны можно использовать в наших сообществах, таких как
DTS • Cases, 
DTS • Clothes, 
DTS • Goyard, 
и DTS • Samsung.

📅 Сроки розыгрыша:

 • Розыгрыш продлится 1 месяц.

Не упустите шанс выиграть крупные призы и дополнительные бонусы! Участвуйте, собирайте поинты и побеждайте!

📅 Сроки розыгрыша:

 Розыгрыш продлится 1 месяц.

Не упустите шанс выиграть крупные призы и дополнительные бонусы! Участвуйте, собирайте поинты и побеждайте!''')

    def register(self) -> None:
        self.dp.message.register(self.start_command, Command("start"))
        self.dp.callback_query.register(self.confirm, F.data == "confirm")
        self.dp.message.register(self.invite_command, F.text == 'Мой реферал')
        self.dp.message.register(self.count_my_point, F.text == 'Мои баллы')
        self.dp.message.register(self.rank, F.text == 'Мой уровень')
        self.dp.message.register(self.guide, F.text == 'Гид')
        self.dp.callback_query.register(self.handle_privacy_acceptance, F.data == 'accepted')
        self.dp.message.register(self.handle_contact, F.contact)
        self.dp.chat_member.register(self.track_invite)

    async def start_bot(self) -> None:
        self.register()
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            print(f"Error in polling: {e}")
            await self.bot.session.close()

if __name__ == '__main__':
    asyncio.run(ReferralBot(token=BOT_TOKEN).start_bot())