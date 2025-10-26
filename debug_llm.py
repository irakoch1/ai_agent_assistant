import os
import sys

sys.path.append(".")

from llm_client import LLMClient
from config import Config
import logging

# Включаем подробное логирование
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def test_llm_with_text(text):
    print(f"\n🔍 Тестируем: '{text}'")

    client = LLMClient()

    try:
        # Проверяем API ключ
        if not Config.LLM_API_KEY or Config.LLM_API_KEY.startswith("**"):
            print("❌ API ключ не настроен!")
            return

        print(f"✅ API ключ: {Config.LLM_API_KEY[:10]}...")
        print(f"✅ API URL: {Config.LLM_API_URL}")

        # Пробуем сделать запрос
        result = client.extract_event_info(text)
        print(f"✅ Успех! Результат: {result}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_cases = [
        "сегодня в 19.00 пробежка",
        "завтра встреча в 15.00",
        "совещание в 10 утра",
    ]

    for text in test_cases:
        test_llm_with_text(text)
