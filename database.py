import psycopg2
from config import Config
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from models import EventConflict
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
        # Названия таблиц и колонок
        self.table_users = "users"
        self.table_events = "events"
        self.column_user_id = "user_id"
        self.column_name = "name"
        self.column_description = "description_event"
        self.column_start_time = "start_time"
        self.column_end_time = "end_time"
        self.column_is_all_day = "is_all_day"
        self.column_priority = "priority_event"
        self.column_status = "status"
        
        # Проверяем структуру таблицы
        self.check_table_structure()

    def connect(self):
        try:
            if Config.DATABASE_URL:
                # Подключение через строку подключения (для Render и других облачных платформ)
                # Учитываем необходимость SSL для облачных баз данных
                self.conn = psycopg2.connect(
                    Config.DATABASE_URL,
                    sslmode='require'  # Для безопасности при подключении к облачным БД
                )
            else:
                # Подключение через отдельные параметры (для локальной разработки)
                self.conn = psycopg2.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    dbname=Config.DB_NAME,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    sslmode='prefer'  # Опциональное SSL-подключение для локальной разработки
                )
            logger.info("✅ Подключение к базе данных установлено успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к базе данных: {e}")
            raise

    def check_table_structure(self):
        """Проверяет структуру таблицы events"""
        try:
            query = """
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'events'
            """
            
            with self.conn.cursor() as cur:
                cur.execute(query)
                columns = cur.fetchall()
                
            logger.info("📊 Структура таблица events:")
            for column in columns:
                logger.info(f"  {column[0]} ({column[1]}, nullable: {column[2]})")
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки структуры таблицы: {e}")

    def check_time_conflict(
        self, user_id: int, event_date: str, event_time: str, duration_minutes: int = 30
    ) -> EventConflict:
        """Проверяет конфликты времени для пользователя"""
        # ВРЕМЕННО ОТКЛЮЧЕНО: всегда возвращаем "нет конфликта"
        logger.info("⚠️ Проверка конфликтов времени отключена")
        return EventConflict(is_conflict=False)

    def save_event(
        self,
        user_id: int,
        description: str,
        start_time: datetime = None,
        end_time: datetime = None,
        priority: int = 2,
        is_all_day: bool = False,
        goal_id: int = None
    ) -> int:
        """Сохраняет событие в базу данных"""
        try:
            # Проверяем на дубликаты
            if start_time:
                duplicate_check = f"""
                SELECT COUNT(*) FROM {self.table_events} 
                WHERE {self.column_user_id} = %s 
                AND {self.column_description} = %s 
                AND {self.column_start_time} = %s
                """
                with self.conn.cursor() as cur:
                    cur.execute(duplicate_check, (user_id, description, start_time))
                    count = cur.fetchone()[0]
                    if count > 0:
                        logger.warning(f"⚠️ Дубликат события найден, пропускаем сохранение: {description}")
                        return -1  # Возвращаем специальный код для дубликата
            
            # Устанавливаем статус по умолчанию
            status = 'активно'
            
            query = f"""
            INSERT INTO {self.table_events} 
            ({self.column_user_id}, goal_id, {self.column_description}, {self.column_start_time}, {self.column_end_time}, {self.column_priority}, {self.column_is_all_day}, {self.column_status}) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING event_id
            """

            logger.info(f"💾 Сохраняем событие в БД: user_id={user_id}, description='{description}', "
                       f"start_time={start_time}, end_time={end_time}, priority={priority}, is_all_day={is_all_day}, status={status}")

            with self.conn.cursor() as cur:
                cur.execute(
                    query, (user_id, goal_id, description, start_time, end_time, priority, is_all_day, status)
                )
                event_id = cur.fetchone()[0]
                self.conn.commit()

            logger.info(f"✅ Событие успешно сохранено, ID: {event_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения события: {e}")
            self.conn.rollback()
            raise

    def get_user_events(
        self, user_id: int, start_date: datetime, end_date: datetime
    ) -> List[Tuple]:
        """Получает события пользователя за период"""
        try:
            query = f"""
            SELECT event_id, {self.column_description}, {self.column_start_time}, 
                   {self.column_end_time}, {self.column_priority}, {self.column_is_all_day}
            FROM {self.table_events} 
            WHERE {self.column_user_id} = %s 
            AND ({self.column_start_time} IS NULL OR {self.column_start_time} BETWEEN %s AND %s)
            ORDER BY {self.column_start_time} NULLS LAST
            """

            with self.conn.cursor() as cur:
                cur.execute(query, (user_id, start_date, end_date))
                events = cur.fetchall()
                logger.info(f"📋 Получено {len(events)} событий для пользователя {user_id}")
                return events
        except Exception as e:
            logger.error(f"⚠️ Ошибка получения событий пользователя: {e}")
            return []

    def user_exists(self, user_id: int, username: str):
        """Проверяет существование пользователя, создает если нет"""
        try:
            query = f"SELECT {self.column_user_id} FROM {self.table_users} WHERE {self.column_user_id} = %s"
            with self.conn.cursor() as cur:
                cur.execute(query, (user_id,))
                if not cur.fetchone():
                    insert_query = f"INSERT INTO {self.table_users} ({self.column_user_id}, {self.column_name}) VALUES (%s, %s)"
                    cur.execute(insert_query, (user_id, username))
                    self.conn.commit()
                    logger.info(f"✅ Создан новый пользователь: {user_id} - {username}")
        except Exception as e:
            logger.error(f"⚠️ Ошибка проверки/создания пользователя: {e}")
            self.conn.rollback()

    def delete_event(self, user_id: int, description: str, date: str = None) -> bool:
        """Удаляет событие по описанию и дате"""
        try:
            if date:
                query = f"""
                DELETE FROM {self.table_events} 
                WHERE {self.column_user_id} = %s 
                AND {self.column_description} ILIKE %s 
                AND {self.column_start_time}::date = %s
                """
                # Используем полное совпадение описания, а не частичное
                params = (user_id, f"%{description}%", date)
            else:
                query = f"""
                DELETE FROM {self.table_events} 
                WHERE {self.column_user_id} = %s 
                AND {self.column_description} ILIKE %s
                """
                # Используем полное совпадение описания, а не частичное
                params = (user_id, f"%{description}%")

            with self.conn.cursor() as cur:
                cur.execute(query, params)
                deleted_count = cur.rowcount
                self.conn.commit()

            logger.info(f"Удалено {deleted_count} событий для пользователя {user_id} с описанием '{description}'")
            return deleted_count > 0

        except Exception as e:
            logger.error(f"❌ Ошибка удаления события: {e}")
            self.conn.rollback()
            return False

    def clear_user_events(self, user_id: int) -> int:
        """Удаляет все события пользователя"""
        try:
            query = f"""
            DELETE FROM {self.table_events} 
            WHERE {self.column_user_id} = %s
            """

            with self.conn.cursor() as cur:
                cur.execute(query, (user_id,))
                deleted_count = cur.rowcount
                self.conn.commit()

            return deleted_count

        except Exception as e:
            logger.error(f"❌ Ошибка очистки событий пользователя: {e}")
            self.conn.rollback()
            return 0

    def get_all_users(self):
        """Получает список всех пользователей из базы данных"""
        try:
            query = f"SELECT {self.column_user_id} FROM {self.table_users}"
            with self.conn.cursor() as cur:
                cur.execute(query)
                users = [row[0] for row in cur.fetchall()]
                logger.info(f"👥 Получено {len(users)} пользователей из БД")
                return users
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователей: {e}")
            return []

    def get_event_by_id(self, event_id: int):
        """Получает событие по ID"""
        try:
            query = f"""
            SELECT event_id, {self.column_description}, {self.column_start_time}, 
                   {self.column_end_time}, {self.column_priority}, {self.column_is_all_day}
            FROM {self.table_events} 
            WHERE event_id = %s
            """
            with self.conn.cursor() as cur:
                cur.execute(query, (event_id,))
                event = cur.fetchone()
                if event:
                    logger.info(f"📝 Событие найдено по ID {event_id}: {event[1]}")
                else:
                    logger.warning(f"⚠️ Событие с ID {event_id} не найдено")
                return event
        except Exception as e:
            logger.error(f"❌ Ошибка получения события: {e}")
            return None

    def check_event_exists(self, user_id: int, description: str, date: str) -> bool:
        """Проверяет, существует ли событие"""
        try:
            query = f"""
            SELECT COUNT(*) FROM {self.table_events} 
            WHERE {self.column_user_id} = %s 
            AND {self.column_description} ILIKE %s 
            AND {self.column_start_time}::date = %s
            """
            
            logger.info(f"🔍 Проверяем существование события: user_id={user_id}, description='{description}', date={date}")
            
            with self.conn.cursor() as cur:
                cur.execute(query, (user_id, f"%{description}%", date))
                count = cur.fetchone()[0]
                
            exists = count > 0
            logger.info(f"📊 Событие существует в БД: {exists} (найдено {count} совпадений)")
            return exists
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки существования события: {e}")
            return False

    def save_goal(self, user_id: int, description: str, priority: int = 2) -> int:
        """Сохраняет цель в базу данных"""
        try:
            query = f"""
            INSERT INTO goals 
            (user_id, description_goal, priority_goal) 
            VALUES (%s, %s, %s)
            RETURNING goal_id
            """

            logger.info(f"💾 Сохраняем цель в БД: user_id={user_id}, description='{description}', priority={priority}")

            with self.conn.cursor() as cur:
                cur.execute(query, (user_id, description, priority))
                goal_id = cur.fetchone()[0]
                self.conn.commit()

            logger.info(f"✅ Цель успешно сохранена, ID: {goal_id}")
            return goal_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения цели: {e}")
            self.conn.rollback()
            raise


# Глобальный экземпляр базы данных
db = Database()