from datetime import datetime, timedelta
from database import db
from models import LLMResponse, EventConflict
from typing import Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from telegram import Bot
from config import Config
import asyncio
import logging
import re

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=Config.TIMEZONE)
        self.bot = None
        
    def set_bot(self, bot: Bot):
        """Устанавливает экземпляр бота для отправки уведомлений"""
        self.bot = bot
        
    def start(self):
        """Запускает планировщик уведомлений"""
        try:
            # Ежедневное расписание в 10:00
            self.scheduler.add_job(
                self.send_daily_schedule,
                CronTrigger(hour=10, minute=0, timezone=Config.TIMEZONE),
                id='daily_schedule'
            )
            
            self.scheduler.start()
            logger.info("✅ Планировщик уведомлений запущен")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска планировщика: {e}")
    
    async def send_daily_schedule(self):
        """Отправляет ежедневное расписание всем пользователей в 10:00"""
        if not self.bot:
            logger.error("Бот не инициализирован для отправки уведомлений")
            return
            
        try:
            # Получаем всех пользователей
            users = db.get_all_users()
            
            for user_id in users:
                try:
                    await self.send_user_daily_schedule(user_id)
                    await asyncio.sleep(0.1)  # Базовая защита от ограничений Telegram
                except Exception as e:
                    logger.error(f"Ошибка отправки расписания пользователю {user_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка в send_daily_schedule: {e}")
    
    async def send_user_daily_schedule(self, user_id: int):
        """Отправляет ежедневное расписание конкретному пользователю"""
        try:
            # Получаем события на сегодня
            today = datetime.now().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            end_of_day = datetime.combine(today, datetime.max.time())
            
            events = db.get_user_events(user_id, start_of_day, end_of_day)
            
            if not events:
                # Нет событий на сегодня
                message = "📅 На сегодня у вас нет запланированных событий. Хорошего дня! 🌞"
            else:
                # Формируем сообщение с событиями
                message = "📅 Ваше расписание на сегодня:\n\n"
                # Регулярное выражение для удаления ведущего времени из описания
                time_prefix_re = re.compile(r"^\s*(в\s*)?([01]?\d|2[0-3])([:.]\d{2})?\s*[-—:]?\s*", re.IGNORECASE)
                
                for event in events:
                    event_id, event_description, start_time, end_time, event_priority, is_all_day = event
                    
                    if is_all_day:
                        event_time_str = "📅 Весь день"
                    else:
                        event_time_str = start_time.strftime("%H:%M")
                        # Убираем возможное повторение времени или шаблон диапазона в начале описания
                        event_description = time_prefix_re.sub("", event_description).strip()
                        event_description = re.sub(r"^\s*с\s*\d{1,2}([:.]\d{2})?\s*(утра|утром|дня|вечера|вечер|ночи|ночью)?\s*(до|–|-|—)\s*\d{1,2}([:.]\d{2})?\s*(утра|утром|дня|вечера|вечер|ночи|ночью)?\s*", "", event_description, flags=re.IGNORECASE).strip()
                    
                    message += f"• {event_time_str} - {event_description}\n"
                
                message += "\nХорошего дня! 🚀"
            
            # Отправляем сообщение
            await self.bot.send_message(chat_id=user_id, text=message)
            
        except Exception as e:
            logger.error(f"Ошибка отправки ежедневного расписания пользователю {user_id}: {e}")
    
    def schedule_event_notification(self, user_id: int, event_id: int, event_time: datetime):
        """Планирует уведомление за час до события"""
        if not self.bot:
            logger.error("Бот не инициализирован для уведомлений о событиях")
            return
            
        try:
            # Для событий на весь день не планируем уведомления
            event = db.get_event_by_id(event_id)
            if event and event[5]:  # event[5] - это is_all_day
                logger.info(f"⚠️ Событие {event_id} на весь день - уведомление не планируется")
                return
                
            # Время уведомления - за час до события
            notification_time = event_time - timedelta(hours=1)
            
            # Если время уведомления уже прошло, не планируем
            if notification_time <= datetime.now():
                return
                
            # Планируем уведомление
            self.scheduler.add_job(
                self.send_event_reminder,
                DateTrigger(run_date=notification_time, timezone=Config.TIMEZONE),
                args=[user_id, event_id],
                id=f'event_reminder_{event_id}'
            )
            
            logger.info(f"✅ Запланировано уведомление для события {event_id} в {notification_time}")
            
        except Exception as e:
            logger.error(f"Ошибка планирования уведомления: {e}")
    
    async def send_event_reminder(self, user_id: int, event_id: int):
        """Отправляет напоминание о событии за час до начала"""
        try:
            # Получаем информацию о событии
            event = db.get_event_by_id(event_id)
            
            if event and not event[5]:  # event[5] - это is_all_day, проверяем что не на весь день
                event_time = event[2].strftime("%H:%M")
                event_description = event[1]
                
                message = f"⏰ Напоминание!\n\nЧерез час у вас запланировано:\n• {event_time} - {event_description}\n\nНе забудьте! 📋"
                
                await self.bot.send_message(chat_id=user_id, text=message)
                logger.info(f"✅ Отправлено напоминание пользователю {user_id} о событии {event_id}")
                
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
    
    def cancel_event_notification(self, event_id: int):
        """Отменяет запланированное уведомление для события"""
        try:
            job_id = f'event_reminder_{event_id}'
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"✅ Отменено уведомление для события {event_id}")
        except Exception as e:
            logger.error(f"Ошибка отмены уведомления: {e}")

    @staticmethod
    def process_event(
        user_id: int, llm_response: LLMResponse, username: str, goal_id: int = None
    ) -> Dict[str, Any]:
        """Основной метод обработки события"""
        # Проверяем/создаем пользователя
        db.user_exists(user_id, username)

        # ВРЕМЕННО: Полностью отключаем проверку конфликтов
        logger.info("⚠️ ВРЕМЕННО: Проверка конфликтов полностью отключена")
        conflict = EventConflict(is_conflict=False)

        # Если время не указано (???), сохраняем как событие на весь день
        if llm_response.time == "???":
            logger.info(f"🔄 Сохраняем событие на весь день: '{llm_response.description}' на {llm_response.date}")

            try:
                # Создаем datetime для начала дня
                start_time = datetime.strptime(f"{llm_response.date} 00:00:00", "%Y-%m-%d %H:%M:%S")
                end_time = datetime.strptime(f"{llm_response.date} 23:59:59", "%Y-%m-%d %H:%M:%S")
                
                event_id = db.save_event(
                    user_id=user_id,
                    description=llm_response.description,
                    start_time=start_time,
                    end_time=end_time,
                    priority=llm_response.priority,
                    is_all_day=True,
                    goal_id=goal_id
                )

                # Проверяем на дубликат
                if event_id == -1:
                    logger.warning(f"⚠️ Дубликат события на весь день пропущен: {llm_response.description}")
                    return {
                        "success": True,
                        "message": f"Событие '{llm_response.description}' уже существует в расписании",
                        "event_id": None,
                        "is_all_day": True,
                        "duplicate": True
                    }

                logger.info(f"✅ Событие на весь день успешно сохранено, ID: {event_id}")

                return {
                    "success": True,
                    "message": f"Событие '{llm_response.description}' запланировано на {llm_response.date}",
                    "event_id": event_id,
                    "is_all_day": True
                }
                
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения события на весь день: {e}")
                return {
                    "success": False,
                    "message": f"Не удалось сохранить событие: {e}",
                    "is_all_day": True
                }

        # Сохраняем событие с временем
        start_time = datetime.strptime(
            f"{llm_response.date} {llm_response.time}", "%Y-%m-%d %H:%M:%S"
        )
        if llm_response.end_time:
            end_time = datetime.strptime(
                f"{llm_response.date} {llm_response.end_time}", "%Y-%m-%d %H:%M:%S"
            )
            # Если конец раньше начала, предполагаем, что это следующий день
            if end_time <= start_time:
                end_time += timedelta(days=1)
        else:
            # Если время окончания не указано, по умолчанию событие длится 1 час
            end_time = start_time + timedelta(hours=1)

        try:
            event_id = db.save_event(
                user_id=user_id,
                description=llm_response.description,
                start_time=start_time,
                end_time=end_time,
                priority=llm_response.priority,
                is_all_day=False,
                goal_id=goal_id
            )

            # Проверяем на дубликат
            if event_id == -1:
                logger.warning(f"⚠️ Дубликат события пропущен: {llm_response.description}")
                return {
                    "success": True,
                    "message": f"Событие '{llm_response.description}' уже существует в расписании",
                    "event_id": None,
                    "is_all_day": False,
                    "duplicate": True
                }

            # Планируем уведомление за час до события
            scheduler_instance.schedule_event_notification(user_id, event_id, start_time)

            return {
                "success": True,
                "message": (
                    f"Событие '{llm_response.description}' запланировано на {llm_response.date} "
                    f"{start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')}" if end_time > start_time else
                    f"Событие '{llm_response.description}' запланировано на {llm_response.date} {start_time.strftime('%H:%M')}"
                ),
                "event_id": event_id,
                "is_all_day": False
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения события с временем: {e}")
            return {
                "success": False,
                "message": f"Не удалось сохранить событие: {e}",
                "is_all_day": False
            }


# Глобальный экземпляр планировщика
scheduler_instance = Scheduler()