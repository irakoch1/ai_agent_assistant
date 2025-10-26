import requests
import json
import re
from datetime import datetime, timedelta
from config import Config
from models import LLMResponse
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.api_key = Config.LLM_API_KEY
        self.api_url = Config.LLM_API_URL
        self.model = Config.LLM_MODEL
    
    def extract_event_info(self, text: str) -> LLMResponse:
        """Отправляет запрос к LLM для извлечения структурированной информации"""
        try:
            prompt = f"""
            Анализируй текст и извлекай информацию о событии. Текст: "{text}"
            
            Сегодня: {datetime.now().strftime('%Y-%m-%d')}
            
            Верни ТОЛЬКО JSON:
            {{
                "date": "YYYY-MM-DD",
                "time": "HH:MM:SS",
                "end_time": "HH:MM:SS",
                "description": "описание",
                "priority": 2,
                "original_text": "текст"
            }}
            
            ПРАВИЛА:
            1. ИЗВЛЕКАЙ ТОЛЬКО КОНКРЕТНЫЕ СОБЫТИЯ. Запросы вроде "спланируй отпуск" или "что мне делать" не являются конкретными событиями.
            2. ВАЖНО: Если текст - бессмыслица (набор случайных букв, нет распознаваемых слов), ИЛИ это общий вопрос, немедленно верни ТОЛЬКО `{{"description": "???"}}` и больше ничего.
            3. Найди ГЛАВНОЕ ДЕЙСТВИЕ (глагол): встать, идти, встреча, пробежка, обед и т.д.
            4. Найди МЕСТО/НАПРАВЛЕНИЕ: в столовую, в буфет, в сбер, домой и т.д.
            5. Объедини в краткое описание: "встать", "идти в буфет", "встреча в офисе"
            6. НЕ включай время в описание ("в 16", "16:00" убирать)
            7. НЕ включай дату в описание ("завтра", "после завтра" убирать)
            8. Если это НЕ бессмыслица, исправляй орфографические ошибки и опечатки в описании.
            
            ПРАВИЛА ВРЕМЕНИ:
            1. Если время НЕ указано явно - ставить "???" для time и null для end_time.
            2. Если указан диапазон (например, "с 9 до 18"), извлеки time как время начала и end_time как время окончания.
            3. Если указано только время начала, end_time должно быть null.
            4. Время указывать ТОЛЬКО если есть цифры (10, 15:30 и т.д.)
            5. "утром", "днем", "вечером" - НЕ считается указанием времени
            
            ПРАВИЛА ДАТЫ:
            1. "после завтра" = через 2 дня от сегодня
            2. "завтра" = через 1 день от сегодня
            3. "сегодня" = сегодняшний день
            
            ПРИМЕРЫ:
            "После завтра встать в 7 утра" → description: "встать", date: через 2 дня, time: "07:00:00", end_time: null
            "Завтра иду в буфет в 16" → description: "идти в буфет", date: завтра, time: "16:00:00", end_time: null
            "29 сентября с 9 до 18 работа" → description: "работа", date: "2025-09-29", time: "09:00:00", end_time: "18:00:00"
            "спланируй отпуск" → description: "???"
            "абырвалг" → description: "???"
            """

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500
            }

            logger.debug(f"Отправляю запрос к LLM для извлечения данных: {text}")
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            llm_data = response.json()
            content = llm_data['choices'][0]['message']['content'].strip()
            logger.debug(f"Ответ LLM для извлечения: {content}")
            
            # Очищаем ответ от markdown
            cleaned_content = content.replace('```json', '').replace('```', '').strip()
            
            # Парсим JSON
            data = json.loads(cleaned_content)

            if data.get("description") == "???":
                return LLMResponse(
                    date=datetime.now().strftime("%Y-%m-%d"),
                    time="???",
                    description="???",
                    priority=2,
                    original_text=text
                )
            
            # Валидируем через Pydantic модель
            return LLMResponse(**data)
            
        except Exception as e:
            logger.error(f"Ошибка извлечения данных LLM: {e}")
            # Fallback на упрощенный парсинг
            return self.simple_event_parse(text)

    def generate_training_plan(self, goal: str) -> list[dict]:
        """Генерирует план тренировок для достижения цели"""
        try:
            prompt = f"""
            Ты — ассистент по планированию. Твоя задача — помочь пользователю достичь своей цели, составив для него пошаговый план.

            Пользователь поставил себе цель: '{goal}'.
            Сегодняшняя дата: {datetime.now().strftime('%Y-%m-%d')}.

            Составь реалистичный план для достижения этой цели. План должен состоять из нескольких шагов (событий).

            План должен быть в виде JSON-массива, где каждый элемент - это событие с полями "date" (в формате YYYY-MM-DD) и "description".
            Описание каждого шага должно быть коротким, ясным и измеримым.

            Пример:
            Если цель "выучить 100 новых английских слов за 10 дней", план может быть таким:
            [
              {{"date": "2025-09-27", "description": "Выучить 10 новых английских слов"}},
              {{"date": "2025-09-28", "description": "Повторить вчерашние 10 слов и выучить 10 новых"}},
              {{"date": "2025-09-29", "description": "Выучить 10 новых английских слов на тему 'Еда'"}}
            ]

            Верни ТОЛЬКО JSON-массив.
            """

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [{"role": "system", "content": "Ты — ассистент по планированию."}, {"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 1000
            }

            logger.debug(f"Отправляю запрос к LLM для генерации плана: {goal}")
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            llm_data = response.json()
            content = llm_data['choices'][0]['message']['content'].strip()
            logger.debug(f"Ответ LLM для генерации плана: {content}")
            
            cleaned_content = content.replace('```json', '').replace('```', '').strip()
            
            plan = json.loads(cleaned_content)
            return plan

        except Exception as e:
            logger.error(f"Ошибка генерации плана тренировок: {e}")
            return []
    
    def simple_event_parse(self, text: str) -> LLMResponse:
        """Упрощенный парсинг событий когда LLM не работает"""
        
        def is_gibberish(text: str) -> bool:
            # Простая эвристика для определения бессмыслицы
            text = text.lower()
            vowels = "аеёиоуыэюяaeiou"
            consonants = "бвгджзйклмнпрстфхцчшщbcdfghjklmnpqrstvwxyz"
            
            vowel_count = sum(1 for char in text if char in vowels)
            consonant_count = sum(1 for char in text if char in consonants)
            digit_count = sum(1 for char in text if char.isdigit())
            
            # Считаем, что это не бессмыслица, если есть цифры
            if digit_count > 0:
                return False
                
            # Если гласных нет или их очень мало по сравнению с согласными
            if len(text) > 3 and (vowel_count == 0 or (consonant_count / (vowel_count + 1)) > 2):
                return True
                
            return False

        if is_gibberish(text):
            return LLMResponse(
                date=datetime.now().strftime("%Y-%m-%d"),
                time="???",
                description="???",
                priority=2,
                original_text=text
            )

        try:
            text_lower = text.lower()
            
            # Определяем дату
            today = datetime.now()
            if "после завтра" in text_lower or "послезавтра" in text_lower:
                event_date = (today + timedelta(days=2)).strftime("%Y-%m-%d")
            elif "завтра" in text_lower:
                event_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                event_date = today.strftime("%Y-%m-%d")
            
            # Проверяем, есть ли указание времени (в том числе диапазон "с HH[:MM] [индикатор] до HH[:MM] [индикатор]")
            range_pattern = r"(?:с\s*)?(\d{1,2})(?:[.:](\d{2}))?\s*(утра|утром|дня|вечера|вечер|ночи|ночью)?\s*(?:до|–|-|—)\s*(\d{1,2})(?:[.:](\d{2}))?\s*(утра|утром|дня|вечера|вечер|ночи|ночью)?"
            range_match = re.search(range_pattern, text_lower)
            time_match = re.search(r'(\d{1,2})[.:]?\s*(\d{2})?', text)
            has_time_indicators = any(word in text_lower for word in ['в ', 'во ', 'часов', 'час', 'утра', 'дня', 'вечера', 'вечер', 'ночи', 'ночью'])
            
            # Если есть цифры времени или явные указатели времени - парсим время
            if range_match or time_match or has_time_indicators:
                def normalize_hour_min(h: str, m: str | None, indicator: str | None) -> tuple[int, str]:
                    hour = int(h)
                    minutes = m or "00"
                    # Определяем индикаторы: сначала берем локальный для этого времени, иначе глобально из текста
                    ind = (indicator or "").strip() if indicator else None
                    is_morning = (ind in ['утра','утром']) or ('утра' in text_lower or 'утром' in text_lower)
                    is_afternoon = (ind == 'дня') or ('дня' in text_lower)
                    is_evening = (ind in ['вечера','вечер']) or ('вечера' in text_lower or 'вечер' in text_lower)
                    is_night = (ind in ['ночи','ночью']) or ('ночи' in text_lower or 'ночью' in text_lower)
                    if is_evening or is_afternoon:
                        if 1 <= hour <= 11:
                            hour += 12
                    elif is_night:
                        if hour == 12:
                            hour = 0
                    return hour, minutes

                if range_match:
                    sh, sm = range_match.group(1), range_match.group(2)
                    si = range_match.group(3)
                    eh, em = range_match.group(4), range_match.group(5)
                    ei = range_match.group(6)
                    # Если у конца нет индикатора, наследуем от начала
                    if not ei:
                        ei = si
                    start_hour, start_min = normalize_hour_min(sh, sm, si)
                    end_hour, end_min = normalize_hour_min(eh, em, ei)
                    # Если получился конец <= начала, и индикаторов нет, предположим, что это тот же период и просто не меняем; иначе оставим как есть
                    event_time = f"{start_hour:02d}:{start_min}:00"
                    event_end_time = f"{end_hour:02d}:{end_min}:00"
                elif time_match:
                    hours = time_match.group(1)
                    minutes = time_match.group(2) or "00"
                    hour_int, minutes_val = normalize_hour_min(hours, minutes, None)
                    event_time = f"{hour_int:02d}:{minutes_val}:00"
                    event_end_time = None
                else:
                    # Если есть указатели времени но нет цифр, ставим дефолтное время
                    event_time = "12:00:00"
                    event_end_time = None
            else:
                # События без времени (например, "завтра нужно помедитировать")
                event_time = "???"
                event_end_time = None
            
            # Создаем описание - убираем только временные слова и местоимения
            description = text
            
            # Убираем только временные слова и местоимения в начале
            description = re.sub(r'^(сегодня|завтра|послезавтра|после завтра|я)\s+', '', description, flags=re.IGNORECASE)
            
            # Убираем время в формате "в XX"
            description = re.sub(r'\bв\s+\d{1,2}\b', '', description)
            
            # Убираем лишние пробелы
            description = re.sub(r'\s+', ' ', description).strip()
            
            # Если описание получилось пустым, используем fallback
            if not description or len(description) < 3:
                description = "Событие"
            
            return LLMResponse(
                date=event_date,
                time=event_time,
                end_time=event_end_time,
                description=description,
                priority=2,
                original_text=text
            )
            
        except Exception as e:
            logger.error(f"Ошибка упрощенного парсинга: {e}")
            # Возвращаем дефолтные значения с улучшенным описанием
            today = datetime.now()
            description = text.strip('.,!?;:')
            if len(description) < 2:
                description = "Событие"
                
            return LLMResponse(
                date=today.strftime("%Y-%m-%d"),
                time="???",
                description=description,
                priority=2,
                original_text=text
            )
    
    def generate_human_response(self, event_data: dict, conflict: bool = False, user_text: str = "") -> str:
        """Генерирует человеческий ответ через LLM"""
        
        if not event_data or not event_data.get('description') or event_data.get('description') == "???":
            # Для некорректных запросов возвращаем жестко заданный ответ
            return "Не удалось распознать команду. Попробуйте, например: 'Завтра встреча в 15:00' или 'Послезавтра поход в кино'"

        if conflict:
            # Запрос к LLM для генерации ответа о конфликте (НЕ ИСПОЛЬЗУЕТСЯ - конфликты отключены)
            return f"❌ Время {event_data.get('time')} на {event_data.get('date')} уже занято. Попробуйте другое время."
        
        # Запрос к LLM для генерации подтверждения планирования
        if event_data.get('time') == "???":
            # Для событий без времени
            prompt = f"""
            Ты - ассистент по планированию. Ты только что успешно запланировал(а) событие без конкретного времени для пользователя.
            
            Данные события:
            - Описание: {event_data.get('description')}
            - Дата: {event_data.get('date')}
            - Время: весь день (без конкретного времени)
            
            Придумай креативный, дружелюбный и естественный ответ, подтверждающий успешное планирование.
            Упомяни, что событие запланировано на весь день без конкретного времени.
            Не используй эмодзи, будь позитивным. Не используй шаблонные фразы. Используй не более 3 предложений.
            """
        else:
            # Для событий с временем
            time_part = event_data.get('time')
            end_time = event_data.get('end_time') if event_data.get('end_time') else None
            if end_time:
                time_part = f"{event_data.get('time')[:5]}–{end_time[:5]}"
            prompt = f"""
            Ты - ассистент по планированию. Ты только что успешно запланировал(а) событие для пользователя.
            
            Данные события:
            - Описание: {event_data.get('description')}
            - Дата: {event_data.get('date')}
            - Время: {time_part}
            
            Придумай креативный, дружелюбный и естественный ответ, подтверждающий успешное планирование.
            Не используй эмодзи, будь позитивным. Не используй шаблонные фразы. Используй не более 3 предложений.
            """

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 150
        }

        try:
            logger.debug(f"Отправляю запрос к LLM для генерации ответа")
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            llm_data = response.json()
            content = llm_data['choices'][0]['message']['content'].strip()
            logger.debug(f"Сгенерированный ответ LLM: {content}")
            
            return content
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа LLM: {e}")
            # Фолбэк на простые ответы
            if conflict:
                return "❌ К сожалению, это время уже занято. Давайте выберем другое время!"
            elif not event_data or not event_data.get('description'):
                return "Не совсем понял запрос. Попробуйте сказать, например: 'завтра встреча в 15:00' или 'завтра нужно помедитировать'"
            else:
                if event_data.get('time') == "???":
                    return f"✅ Запланировано на весь день: {event_data.get('description')} на {event_data.get('date')}"
                else:
                    time_str = event_data.get('time', '').replace(':00', '') if event_data.get('time') else ''
                    return f"✅ Запланировано: {event_data.get('description')} на {event_data.get('date')} в {time_str}"

    def is_delete_command(self, text: str) -> bool:
        """Проверяет, является ли текст командой удаления"""
        delete_keywords = ['удали', 'убери', 'remove', 'delete', 'отмени']
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in delete_keywords)

    def extract_event_from_delete(self, text: str) -> str:
        """Извлекает название события из команды удаления"""
        text_lower = text.lower()
        for keyword in ['удали', 'убери', 'remove', 'delete', 'отмени']:
            if keyword in text_lower:
                return text_lower.replace(keyword, '').strip()
        return text.strip()

    def extract_delete_intent(self, text: str) -> dict:
        """Определяет intent удаления события"""
        delete_keywords = ['удали', 'убери', 'remove', 'delete', 'отмени', 'отмена']
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in delete_keywords):
            # Извлекаем описание события для удаления и возможную дату
            pattern = r'(удали|убери|remove|delete|отмени|отмена)\s+(.*)'
            match = re.search(pattern, text_lower)
            
            if match:
                full_description = match.group(2).strip()
                
                # Ищем дату в описании
                date_pattern = r'(сегодня|завтра|послезавтра|после завтра)'
                date_match = re.search(date_pattern, full_description)
                
                if date_match:
                    date_text = date_match.group(1)
                    event_description = re.sub(date_pattern, '', full_description).strip()
                    # Убираем лишние пробелы и союзы
                    event_description = re.sub(r'^в\s*', '', event_description)
                    event_description = re.sub(r'^на\s*', '', event_description)
                    
                    # Преобразуем текстовую дату в формат YYYY-MM-DD
                    today = datetime.now().date()
                    
                    if date_text == 'сегодня':
                        event_date = today.strftime('%Y-%m-%d')
                    elif date_text == 'завтра':
                        event_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                    elif date_text in ['послезавтра', 'после завтра']:
                        event_date = (today + timedelta(days=2)).strftime('%Y-%m-%d')
                    else:
                        event_date = None
                        
                    return {
                        'intent': 'delete',
                        'description': event_description,
                        'date': event_date
                    }
                else:
                    # Проверяем, может быть, в описании есть дата в формате DD.MM.YYYY или YYYY-MM-DD
                    date_patterns = [
                        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
                        r'(\d{2}\.\d{2}\.\d{4})',  # DD.MM.YYYY
                        r'(\d{2}/\d{2}/\d{4})'   # DD/MM/YYYY
                    ]
                    
                    for date_pattern in date_patterns:
                        date_match = re.search(date_pattern, full_description)
                        if date_match:
                            event_date = date_match.group(1)
                            # Конвертируем DD.MM.YYYY или DD/MM/YYYY в YYYY-MM-DD, если нужно
                            if '.' in event_date or '/' in event_date:
                                parts = re.split(r'[.\-/]', event_date)
                                if len(parts) == 3:
                                    if len(parts[2]) == 4:  # Год в формате YYYY
                                        event_date = f"{parts[2]}-{parts[1]:>02s}-{parts[0]:>02s}"
                            
                            event_description = re.sub(date_pattern, '', full_description).strip()
                            # Убираем лишние пробелы и союзы
                            event_description = re.sub(r'^в\s*', '', event_description)
                            event_description = re.sub(r'^на\s*', '', event_description)
                            
                            return {
                                'intent': 'delete',
                                'description': event_description,
                                'date': event_date
                            }
                    
                    # Если дата не найдена, возвращаем без даты
                    return {
                        'intent': 'delete',
                        'description': full_description,
                        'date': None
                    }
        
        return {'intent': 'unknown'}

    def is_meaningful_goal(self, goal_text: str) -> bool:
        """Проверяет, является ли цель осмысленной"""
        try:
            # Простая эвристика для определения бессмыслицы
            def is_gibberish(text: str) -> bool:
                text = text.lower().strip()
                vowels = "аеёиоуыэюяaeiou"
                consonants = "бвгджзйклмнпрстфхцчшщbcdfghjklmnpqrstvwxyz"
                
                vowel_count = sum(1 for char in text if char in vowels)
                consonant_count = sum(1 for char in text if char in consonants)
                digit_count = sum(1 for char in text if char.isdigit())
                
                # Считаем, что это не бессмыслица, если есть цифры
                if digit_count > 0:
                    return False
                    
                # Если гласных нет или их очень мало по сравнению с согласными
                if len(text) > 3 and (vowel_count == 0 or (consonant_count / (vowel_count + 1)) > 2.5):
                    return True
                    
                # Проверяем, есть ли хотя бы несколько осмысленных слов
                meaningful_indicators = [
                    'дня', 'недели', 'месяца', 'года', 'дней', 'часа', 'часов', 'минут', 'лет',
                    'изучить', 'выучить', 'пробежать', 'бегать', 'читать', 'чита', 'готовить',
                    'подготовиться', 'достичь', 'сделать', 'купить', 'посетить', 'приготовить',
                    'day', 'week', 'month', 'year', 'hour', 'minute', 'learn', 'study', 'run',
                    'read', 'prepare', 'achieve', 'do', 'buy', 'visit', 'cook', 'make'
                ]
                
                text_lower = text.lower()
                has_meaningful = any(indicator in text_lower for indicator in meaningful_indicators)
                
                return not has_meaningful

            if is_gibberish(goal_text):
                return False

            # Также используем LLM для проверки осмысленности
            prompt = f"""
            Ты - фильтр целей. Определи, является ли цель осмысленной.

            Цель: "{goal_text}"

            Ответь ТОЛЬКО "ДА" если цель осмысленна или "НЕТ" если цель бессмысленна/абсурдна/непонятна.

            Осмысленные цели обычно:
            - Описывают конкретное достижение
            - Содержат глагол действия (изучить, пробежать, подготовиться и т.д.)
            - Имеют срок или количество (30 дней, 100 слов, за месяц и т.д.)
            - Понятны и логичны

            Примеры осмысленных целей:
            - выучить 100 английских слов за 30 дней
            - пробежать марафон за 42 минуты
            - подготовиться к экзамену по математике
            - прочитать 12 книг за год

            Примеры бессмысленных целей:
            - саывыогпо
            - Jgjgvjgknhlk
            - абракадабра 123
            - бегать если нет ног

            Ответь: ДА или НЕТ
            """

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 100
            }

            logger.debug(f"Отправляю запрос к LLM для проверки осмысленности цели: {goal_text}")
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            llm_data = response.json()
            content = llm_data['choices'][0]['message']['content'].strip()
            logger.debug(f"Ответ LLM для проверки осмысленности: {content}")
            
            return "ДА" in content.upper()

        except Exception as e:
            logger.error(f"Ошибка проверки осмысленности цели: {e}")
            # В случае ошибки, возвращаем True, чтобы не блокировать пользователя полностью
            return True


# Глобальный экземпляр
llm_client = LLMClient()