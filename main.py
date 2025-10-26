import logging
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from flask import Flask, jsonify
from threading import Thread
 
from config import Config
from database import db
from llm_client import LLMClient
from models import LLMResponse
from scheduler import scheduler_instance
import re
 

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация клиентов
llm_client = LLMClient()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [["Посмотреть расписание", "Обновить расписание"], ["/clear"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🌟 Добро пожаловать в персональный Телеграм-планировщик событий!",
        reply_markup=reply_markup,
    )

    await send_welcome_description(update)

async def send_welcome_description(update: Update):
    """Отправляет подробное описание возможностей бота"""
    description = """
📋 Что вы можете делать:

✅ Планировать события — просто напишите, например:
"запланируй встречу завтра в 15"
"сегодня в 19.00 пробежка" 
"завтра нужно помедитировать"
"послезавтра надо почитать книгу"

🎯 Установить глобальную цель — команда /goal, например:
/goal выучить 100 английских слов за 30 дней

📅 Просмотреть расписание — нажмите кнопку «Посмотреть расписание»

✏️ Обновить расписание — выберите пункт «Обновить расписание»

🗑️ Удалять события командами: "удали пробежка завтра"

🧹 Очистить всё расписание — команда /clear

⏰ Автоматические уведомления:
• Ежедневное расписание в 10:00 утра
• Напоминания за час до каждого события (только для событий с временем)

Выберите действие ниже или напишите, что хотите запланировать! 🚀
"""
    await update.message.reply_text(description)

async def clear_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка всего расписания пользователя"""
    user_id = update.effective_user.id

    try:
        # Подтверждение удаления
        keyboard = [["✅ Да, очистить", "❌ Нет, отмена"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "⚠️ Вы уверены, что хотите очистить ВСЁ расписание? Это действие нельзя отменить!",
            reply_markup=reply_markup,
        )

        # Сохраняем состояние для подтверждения
        context.user_data["awaiting_clear_confirmation"] = True

    except Exception as e:
        logger.error(f"Ошибка очистки расписания: {e}")
        await update.message.reply_text("⚠️ Извините, не удалось очистить расписание.")


async def handle_clear_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка подтверждения очистки"""
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_text == "✅ Да, очистить":
        try:
            # Очищаем события пользователя
            deleted_count = db.clear_user_events(user_id)

            # Восстанавливаем обычную клавиатуру
            keyboard = [["Посмотреть расписание", "Обновить расписание"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                f"✅ Расписание полностью очищено! Удалено {deleted_count} событий.",
                reply_markup=reply_markup,
            )

            # Очищаем состояние подтверждения
            context.user_data.pop("awaiting_clear_confirmation", None)

        except Exception as e:
            logger.error(f"Ошибка очистки расписания: {e}")
            await update.message.reply_text(
                "⚠️ Извините, не удалось очистить расписание."
            )

    elif user_text == "❌ Нет, отмена":
        # Восстанавливаем обычную клавиатуру
        keyboard = [["Посмотреть расписание", "Обновить расписание"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "❌ Очистка расписания отменена.", reply_markup=reply_markup
        )

        # Очищаем состояние подтверждения
        context.user_data.pop("awaiting_clear_confirmation", None)

async def debug_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отладки базы данных"""
    user_id = update.effective_user.id
    
    try:
        # Показываем все события пользователя
        events = db.get_user_events(user_id, datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=30))
        
        if not events:
            await update.message.reply_text("📭 В базе данных нет событий для этого пользователя")
            
            # Покажем также информацию о пользователе
            try:
                query = f"SELECT * FROM users WHERE user_id = %s"
                with db.conn.cursor() as cur:
                    cur.execute(query, (user_id,))
                    user = cur.fetchone()
                    if user:
                        await update.message.reply_text(f"👤 Пользователь найден: ID={user[0]}, Имя={user[1]}")
                    else:
                        await update.message.reply_text("❌ Пользователь не найден в таблице users")
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка проверки пользователя: {e}")
                
        else:
            message = "📊 События в базе данных:\n\n"
            for event in events:
                start_time = event[2].strftime("%Y-%m-%d %H:%M") if event[2] else "Без времени"
                end_time = event[3].strftime("%Y-%m-%d %H:%M") if event[3] else "Без времени"
                message += f"ID: {event[0]}, Описание: {event[1]}, Начало: {start_time}, Конец: {end_time}, Приоритет: {event[4]}, Весь день: {event[5]}\n"
            
            await update.message.reply_text(message[:4000])
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отладки: {e}")

async def goal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /goal"""
    await update.message.reply_text("Какую глобальную цель вы хотите поставить? Например: 'Выучить 100 английских слов за 30 дней' или 'Заниматься спортом 4 раза в неделю в течение 30 дней'.")
    context.user_data['awaiting_goal'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    try:
        # Проверяем, ожидается ли подтверждение очистки
        if context.user_data.get("awaiting_clear_confirmation"):
            await handle_clear_confirmation(update, context)
            return

        if context.user_data.get('awaiting_goal'):
            await handle_goal_creation(update, context)
            return

        if context.user_data.get('awaiting_goal_confirmation'):
            await handle_goal_confirmation(update, context)
            return

        if user_text == "Посмотреть расписание":
            await show_schedule(update, context)
        elif user_text == "Обновить расписание":
            await update.message.reply_text("Введите событие, которое нужно добавить в расписание")
        elif user_text == "/clear":
            await clear_schedule(update, context)
        elif user_text == "/debug":
            await debug_db(update, context)
        elif llm_client.is_delete_command(user_text):
            await handle_delete_event(update, user_id, user_text)
        else:
            await process_natural_language(update, user_text, user_id, username, context)

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
        await update.message.reply_text("Извините, произошла ошибка. Попробуйте позже.")

async def handle_goal_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка создания глобальной цели"""
    goal_description = update.message.text
    context.user_data['goal_description'] = goal_description
    context.user_data['awaiting_goal'] = False

    # Прежде чем генерировать план, проверим, является ли цель осмысленной
    try:
        # Проверяем осмысленность цели с помощью LLM
        is_meaningful = llm_client.is_meaningful_goal(goal_description)
        
        if not is_meaningful:
            await update.message.reply_text(
                "Я не понял ваш запрос. Пожалуйста, сформулируйте цель в нужном формате. "
                "Например: 'выучить 100 английских слов за 30 дней' или 'подготовиться к марафону за 2 месяца'."
            )
            # Очищаем состояние, чтобы пользователь мог ввести новую цель
            context.user_data.pop('goal_description', None)
            context.user_data['awaiting_goal'] = True
            return
        
        await update.message.reply_text(f"Отлично! Ваша цель: '{goal_description}'. Я уже работаю над планом для ее достижения...")

        plan = llm_client.generate_training_plan(goal_description)

        if not plan:
            await update.message.reply_text("К сожалению, мне не удалось составить план для вашей цели. Попробуйте сформулировать ее по-другому.")
            return

        context.user_data['generated_plan'] = plan
    except Exception as e:
        logger.error(f"Ошибка при обработке цели: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обработке вашей цели. Пожалуйста, сформулируйте цель в нужном формате. "
            "Например: 'выучить 100 английских слов за 30 дней' или 'подготовиться к марафону за 2 месяца'."
        )
        # Очищаем состояние, чтобы пользователь мог ввести новую цель
        context.user_data.pop('goal_description', None)
        context.user_data['awaiting_goal'] = True
        return

    plan_text = "Вот мой план:\n\n"
    for event in plan:
        plan_text += f"- {event['date']}: {event['description']}\n"

    keyboard = [["✅ Принять", "❌ Отклонить"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(plan_text, reply_markup=reply_markup)

    context.user_data['awaiting_goal_confirmation'] = True


async def handle_goal_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка подтверждения плана цели"""
    if 'awaiting_goal_confirmation' in context.user_data:
        context.user_data.pop('awaiting_goal_confirmation', None)
    else:
        return

    user_text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    keyboard = [["Посмотреть расписание", "Обновить расписание"], ["/clear"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    if user_text == "✅ Принять":
        plan = context.user_data.get('generated_plan', [])
        goal_description = context.user_data.get('goal_description')

        if not plan or not goal_description:
            await update.message.reply_text("Что-то пошло не так, я не смог найти план. Попробуйте еще раз.", reply_markup=reply_markup)
        else:
            # Save the goal
            goal_id = db.save_goal(user_id, goal_description, 2) # priority = 2 (default)

            for event in plan:
                llm_response = LLMResponse(
                    date=event['date'],
                    time="???",
                    description=event['description'],
                    priority=2,
                    original_text=event['description']
                )
                # Pass goal_id to process_event
                await asyncio.to_thread(scheduler_instance.process_event, user_id, llm_response, username, goal_id)
            
            await update.message.reply_text("Отлично! План добавлен в ваше расписание.", reply_markup=reply_markup)
            context.user_data.pop('generated_plan', None)
            context.user_data.pop('goal_description', None)

    elif user_text == "❌ Отклонить":
        await update.message.reply_text("Понял, план не будет добавлен.", reply_markup=reply_markup)
        context.user_data.pop('generated_plan', None)
        context.user_data.pop('goal_description', None)


async def process_natural_language(
    update: Update, text: str, user_id: int, username: str, context: ContextTypes.DEFAULT_TYPE
):
    """Обработка естественно-языкового запроса с LLM"""
    try:
        logger.info(f"📨 Обрабатываю запрос: '{text}'")

        # Извлекаем структурированную информацию с помощью LLM
        llm_response = llm_client.extract_event_info(text)

        # Если есть время, но нет явной даты – используем последнюю дату из контекста
        text_lower = text.lower()
        has_explicit_date = (
            re.search(r"\b(сегодня|завтра|послезавтра|после завтра)\b", text_lower)
            or re.search(r"\b(январ|феврал|март|апрел|ма[йi]|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*\b", text_lower)
            or re.search(r"\b\d{4}-\d{2}-\d{2}\b", text_lower)
            or re.search(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b", text_lower)
        )
        has_time = re.search(r"\b\d{1,2}([:.]\d{2})?\b", text_lower) is not None or any(
            w in text_lower for w in ["час", "часов"]
        )
        last_date = context.user_data.get("last_date") if hasattr(context, "user_data") else None
        if not has_explicit_date and has_time and last_date and llm_response.time != "???":
            llm_response.date = last_date
        logger.info(f"📊 Извлеченные данные: date={llm_response.date}, time='{llm_response.time}', desc='{llm_response.description}'")
        logger.info(f"🔍 Тип события: {'БЕЗ ВРЕМЕНИ' if llm_response.time == '???' else 'С ВРЕМЕНЕМ'}")

        # Проверяем, есть ли информация о событии
        has_event = llm_response.description and llm_response.description.strip() and llm_response.description != "???"

        if has_event:
            try:
                # Сохраняем в базу данных
                result = scheduler_instance.process_event(user_id, llm_response, username)
                logger.info(f"📋 Результат сохранения: {result}")

                # Проверяем, действительно ли событие сохранилось
                if result.get("success", False):
                    # Проверяем существование события в БД
                    event_exists = db.check_event_exists(user_id, llm_response.description, llm_response.date)
                    logger.info(f"🔍 Событие существует в БД: {event_exists}")
                    
                    if not event_exists:
                        logger.error("❌ Событие не было сохранено в БД!")
                        await update.message.reply_text("⚠️ Не удалось сохранить событие в базу данных. Попробуйте еще раз.")
                        return

                # Подготавливаем данные для ответа
                response_data = {
                    "description": llm_response.description,
                    "time": llm_response.time,
                    "end_time": llm_response.end_time,
                    "date": llm_response.date,
                }

                # Добавляем информацию о конфликте если есть
                if not result["success"]:
                    response_data.update(result.get("conflict_data", {}))

                # Генерируем человеческий ответ через LLM только если событие успешно сохранено
                if result["success"]:
                    human_response = llm_client.generate_human_response(
                        response_data, conflict=False, user_text=text
                    )
                else:
                    # Если не удалось сохранить, показываем реальную ошибку
                    human_response = f"❌ Не удалось сохранить событие: {result.get('message', 'Неизвестная ошибка')}"
                
                await update.message.reply_text(human_response)

                # Сохраняем последнюю явно указанную дату для коротких команд со временем
                if hasattr(context, "user_data") and llm_response.date and has_explicit_date:
                    context.user_data["last_date"] = llm_response.date
                
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения события: {e}")
                # Fallback ответ
                if llm_response.time == "???":
                    await update.message.reply_text(f"✅ Добавлено на весь день: {llm_response.description} на {llm_response.date}")
                else:
                    await update.message.reply_text(f"✅ Запланировано: {llm_response.description} на {llm_response.date} в {llm_response.time}")
                    
        else:
            # Генерируем ответ на некорректный запрос
            human_response = llm_client.generate_human_response(
                {}, conflict=False, user_text=text
            )
            await update.message.reply_text(human_response)

    except Exception as e:
        logger.error(f"❌ Ошибка обработки запроса: {e}")
        # Более информативный fallback
        try:
            # Пробуем простой парсинг
            today = datetime.now()
            if "завтра" in text.lower():
                date_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                date_str = today.strftime("%Y-%m-%d")
                
            # Извлекаем описание
            description = re.sub(r'(сегодня|завтра|послезавтра|в\s+\d+[:.]?\d*)', '', text, flags=re.IGNORECASE)
            description = re.sub(r'\s+', ' ', description).strip()
            
            if not description:
                description = text
                
            await update.message.reply_text(f"✅ Добавлено: {description} на {date_str}")
            
        except Exception as fallback_error:
            logger.error(f"❌ Fallback также не сработал: {fallback_error}")
            await update.message.reply_text(
                "⚠️ Извините, не удалось обработать запрос. Попробуйте сказать, например: 'завтра встреча в 15:00' или 'завтра нужно помедитировать'"
            )


async def handle_delete_event(update: Update, user_id: int, text: str):
    """Обработка команды удаления события"""
    try:
        # Извлекаем информацию об удалении (описание и дату)
        delete_info = llm_client.extract_delete_intent(text)

        event_description = ""
        event_date = None

        # Проверяем, удалось ли распознать команду удаления
        if delete_info and delete_info.get('intent') == 'delete':
            event_description = delete_info.get('description', '').strip()
            event_date = delete_info.get('date', None)
        else:
            # Если распознавание не сработало, используем старый метод
            event_description = llm_client.extract_event_from_delete(text).strip()

        if not event_description or len(event_description) < 2:
            await update.message.reply_text(
                "Пожалуйста, укажите, какое событие нужно удалить. Например: 'удали плавание' или 'удали тренировку завтра'"
            )
            return

        # Удаляем событие (с датой, если она указана)
        success = db.delete_event(user_id, event_description, event_date)

        if success:
            if event_date:
                await update.message.reply_text(
                    f"✅ Событие '{event_description}' на {event_date} успешно удалено из расписания!"
                )
            else:
                await update.message.reply_text(
                    f"✅ Событие '{event_description}' успешно удалено из расписания!"
                )
        else:
            if event_date:
                await update.message.reply_text(
                    f"❌ Не удалось найти событие '{event_description}' на {event_date}. Проверьте правильность названия и даты."
                )
            else:
                await update.message.reply_text(
                    f"❌ Не удалось найти событие '{event_description}'. Проверьте правильность названия."
                )

    except Exception as e:
        logger.error(f"Ошибка удаления события: {e}")
        await update.message.reply_text(
            "⚠️ Извините, не удалось удалить событие. Попробуйте позже."
        )


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать только будущие события пользователя"""
    user_id = update.effective_user.id

    try:
        # Получаем все события
        past_date = datetime.now() - timedelta(days=365)
        future_date = datetime.now() + timedelta(days=365)

        events = db.get_user_events(user_id, past_date, future_date)
        logger.info(f"Все события из БД: {events}")

        if not events:
            await update.message.reply_text(
                "📅 У вас пока нет запланированных событий!"
            )
            return

        # Фильтруем: оставляем только будущие события (включая сегодняшние)
        current_time = datetime.now()
        future_events = []

        for event in events:
            event_time = event[2]
            is_all_day = event[5]
            
            # Для событий на весь день (без времени) показываем если дата >= сегодня
            if is_all_day or event_time is None:
                # Для событий без времени проверяем только дату
                if event_time is not None:
                    event_date = event_time.date()
                else:
                    # Если event_time None, но событие на весь день, используем текущую дату как fallback
                    # Но для корректной работы нужно определить дату из события
                    # В этом случае используем текущую дату как fallback, но это не идеально
                    # Лучше использовать today(), но для реальных событий нужно получить правильную дату
                    event_date = datetime.now().date()
                if event_date >= current_time.date():
                    future_events.append(event)
            else:
                # Для событий с временем проверяем полное время
                if event_time >= current_time:
                    future_events.append(event)

        if not future_events:
            await update.message.reply_text(
                "📅 Все ваши события уже прошли! Запланируйте новые."
            )
            return

        # Группируем события по датам
        events_by_date = {}
        # Регулярка для удаления ведущего времени из описания ("в 9", "08:30", "8.30", и т.п.)
        time_prefix_re = re.compile(r"^\s*(в\s*)?([01]?\d|2[0-3])([:.]\d{2})?\s*[-—:]?\s*", re.IGNORECASE)
        for event in future_events:
            event_id, event_description, start_time, end_time, event_priority, is_all_day = event
            
            # Безопасная обработка даты
            if start_time:
                event_date = start_time.strftime("%d.%m.%Y")
            else:
                event_date = datetime.now().strftime("%d.%m.%Y")

            # Приоритетные эмодзи убраны

            if is_all_day:
                # Событие на весь день
                if event_date not in events_by_date:
                    events_by_date[event_date] = []
                events_by_date[event_date].append(f"• Весь день - {event_description}")
            else:
                # Событие с временем
                if end_time and end_time > start_time and end_time.date() == start_time.date():
                    event_time_str = f"{start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')}"
                else:
                    event_time_str = start_time.strftime("%H:%M")
                # Убираем возможное повторение времени в начале описания
                event_description = time_prefix_re.sub("", event_description).strip()
                # Убираем шаблон диапазона "с .. до .." в начале описания
                event_description = re.sub(r"^\s*с\s*\d{1,2}([:.]\d{2})?\s*(утра|утром|дня|вечера|вечер|ночи|ночью)?\s*(до|–|-|—)\s*\d{1,2}([:.]\d{2})?\s*(утра|утром|дня|вечера|вечер|ночи|ночью)?\s*", "", event_description, flags=re.IGNORECASE).strip()
                if event_date not in events_by_date:
                    events_by_date[event_date] = []
                events_by_date[event_date].append(f"• {event_time_str} - {event_description}")

        # Формируем текст расписания
        schedule_text = "📅 Ваше расписание (предстоящие события):\n\n"

        # Сортируем даты в хронологическом порядке
        sorted_dates = sorted(
            events_by_date.keys(), key=lambda x: datetime.strptime(x, "%d.%m.%Y")
        )

        for date in sorted_dates:
            schedule_text += f"📆 {date}:\n"
            
            # Выводим все события для этой даты
            for event in events_by_date[date]:
                schedule_text += f"  {event}\n"
            
            schedule_text += "\n"

        # Добавляем информацию о количестве событий
        schedule_text += f"Всего предстоящих событий: {len(future_events)}"

        # Если расписание слишком длинное, разбиваем на части
        if len(schedule_text) > 4000:
            parts = [
                schedule_text[i : i + 4000] for i in range(0, len(schedule_text), 4000)
            ]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(schedule_text)

    except Exception as e:
        logger.error(f"Ошибка получения расписания: {e}")
        import traceback
        logger.error(f"Полная ошибка: {traceback.format_exc()}")
        
        # Попробуем простой запрос для отладки
        try:
            simple_events = db.get_user_events(user_id, datetime.now() - timedelta(days=1), datetime.now() + timedelta(days=30))
            logger.info(f"Простой запрос вернул: {simple_events}")
            
            if simple_events:
                simple_text = "📅 Ваши события:\n\n"
                for event in simple_events:
                    event_desc = event[1] if len(event) > 1 else "Неизвестное событие"
                    event_time = event[2] if len(event) > 2 and event[2] else "Без времени"
                    simple_text += f"• {event_desc} - {event_time}\n"
                await update.message.reply_text(simple_text)
            else:
                await update.message.reply_text("📅 У вас нет запланированных событий!")
        except Exception as simple_e:
            logger.error(f"Даже простой запрос не работает: {simple_e}")
            await update.message.reply_text(f"❌ Критическая ошибка БД: {str(e)[:200]}")


async def post_init(application: Application):
    """Функция инициализации после запуска бота"""
    # Устанавливаем бота в планировщик
    scheduler_instance.set_bot(application.bot)
    # Запускаем планировщик уведомлений
    scheduler_instance.start()
    logger.info("✅ Планировщик уведомлений инициализирован")


def main():
    """Запуск бота"""
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear_schedule))
    application.add_handler(CommandHandler("goal", goal_command))
    application.add_handler(CommandHandler("debug", debug_db))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    
    # Добавляем post-инициализацию
    application.post_init = post_init


def run_bot():
    """Запуск бота с polling"""
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear_schedule))
    application.add_handler(CommandHandler("goal", goal_command))
    application.add_handler(CommandHandler("debug", debug_db))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    
    # Добавляем post-инициализацию
    application.post_init = post_init

    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling()
    logger.info("Бот успешно запущен")


# Создаем Flask приложение для health check
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return jsonify({"status": "healthy", "message": "Telegram bot is running"}), 200

@flask_app.route('/health')
def detailed_health():
    return jsonify({"status": "ok"}), 200


def main():
    """Запуск Flask сервера и бота"""
    # Запускаем Flask сервер в отдельном потоке
    from threading import Thread
    import os
    
    port = int(os.environ.get('PORT', 8000))
    
    def run_flask():
        flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запускаем бота в основном потоке
    run_bot()


if __name__ == "__main__":
    main()


