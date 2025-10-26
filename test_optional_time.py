import sys
sys.path.append(".")

from database import db
from llm_client import LLMClient
from scheduler import scheduler_instance
from datetime import datetime

def test_events_without_time():
    """Тестируем создание событий без времени"""
    
    user_id = 891351808
    username = "test_user"
    
    test_cases = [
        "завтра нужно купить молоко",
        "послезавтра встреча с врачом",
        "на следующей неделе сдать отчет",
        "завтра в 15:00 встреча с клиентом",  # С временем для сравнения
    ]
    
    print("🧪 Тестируем события с опциональным временем\n")
    
    for i, text in enumerate(test_cases, 1):
        print(f"📝 Тест {i}: '{text}'")
        
        try:
            # Создаем пользователя если не существует
            db.user_exists(user_id, username)
            
            # Извлекаем информацию через LLM
            llm_client = LLMClient()
            llm_response = llm_client.extract_event_info(text)
            print(f"   LLM ответ: time='{llm_response.time}', date='{llm_response.date}', description='{llm_response.description}'")
            
            # Обрабатываем событие через scheduler
            result = scheduler_instance.process_event(user_id, llm_response, username)
            
            if result.get("success"):
                print(f"   ✅ Успех: {result.get('message')}")
                print(f"   📊 Event ID: {result.get('event_id')}, All day: {result.get('is_all_day')}")
            else:
                print(f"   ❌ Ошибка: {result.get('message')}")
                
        except Exception as e:
            print(f"   💥 Исключение: {e}")
            
        print()

if __name__ == "__main__":
    test_events_without_time()
