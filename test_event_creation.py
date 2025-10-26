import sys
sys.path.append(".")

from database import db
from llm_client import LLMClient
from scheduler import scheduler_instance
from datetime import datetime

def test_event_creation():
    """Тестируем создание события"""
    
    # Тестовые данные
    user_id = 891351808
    username = "test_user"
    text = "завтра в 9 оформляться в сбер"
    
    print(f"🔍 Тестируем создание события: '{text}'")
    
    try:
        # Создаем пользователя если не существует
        db.user_exists(user_id, username)
        print("✅ Пользователь проверен/создан")
        
        # Извлекаем информацию через LLM
        llm_client = LLMClient()
        llm_response = llm_client.extract_event_info(text)
        print(f"✅ LLM ответ: {llm_response}")
        
        # Обрабатываем событие через scheduler
        result = scheduler_instance.process_event(user_id, llm_response, username)
        print(f"✅ Результат обработки: {result}")
        
        if result.get("success"):
            print("🎉 Событие успешно создано!")
            
            # Проверяем в базе
            event_exists = db.check_event_exists(user_id, llm_response.description, llm_response.date)
            print(f"✅ Событие существует в БД: {event_exists}")
        else:
            print(f"❌ Ошибка создания события: {result.get('message')}")
            
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_event_creation()
