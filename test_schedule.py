#!/usr/bin/env python3
"""
Тест для проверки функции показа расписания
"""
import sys
sys.path.append(".")

from database import db
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_schedule_display():
    """Тестирует отображение расписания"""
    print("🔍 Тестируем отображение расписания...")
    
    # Тестовый user_id - используем реальный ID из БД
    test_user_id = 891351808  # Используем ID пользователя с последними событиями
    
    try:
        # Проверяем подключение к БД
        print("✅ Подключение к БД установлено")
        
        # Получаем события
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now() + timedelta(days=30)
        
        print(f"📅 Ищем события с {start_date} по {end_date}")
        
        events = db.get_user_events(test_user_id, start_date, end_date)
        print(f"📋 Найдено событий: {len(events)}")
        
        if events:
            print("\n📝 Список событий:")
            for i, event in enumerate(events):
                print(f"  {i+1}. {event}")
        else:
            print("📭 События не найдены")
            
            # Проверим, есть ли вообще события в БД
            print("\n🔍 Проверяем все события в БД...")
            try:
                with db.conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM events")
                    total_events = cur.fetchone()[0]
                    print(f"📊 Всего событий в БД: {total_events}")
                    
                    if total_events > 0:
                        # Проверяем последние события
                        cur.execute("SELECT user_id, description_event, start_time FROM events ORDER BY event_id DESC LIMIT 10")
                        recent_events = cur.fetchall()
                        print("📋 Последние события:")
                        for event in recent_events:
                            print(f"  User: {event[0]}, Desc: {event[1]}, Time: {event[2]}")
                        
                        # Проверяем события для конкретного пользователя
                        print(f"\n🔍 Ищем события для user_id = {test_user_id}:")
                        cur.execute("SELECT user_id, description_event, start_time FROM events WHERE user_id = %s ORDER BY event_id DESC LIMIT 5", (test_user_id,))
                        user_events = cur.fetchall()
                        if user_events:
                            print("📋 События пользователя:")
                            for event in user_events:
                                print(f"  User: {event[0]}, Desc: {event[1]}, Time: {event[2]}")
                        else:
                            print("📭 У этого пользователя нет событий")
                            
                        # Проверяем всех пользователей
                        cur.execute("SELECT DISTINCT user_id FROM events")
                        all_users = cur.fetchall()
                        print(f"👥 Пользователи в БД: {[u[0] for u in all_users]}")
                        
            except Exception as e:
                print(f"❌ Ошибка проверки БД: {e}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_schedule_display()
