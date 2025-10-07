import google.generativeai as oldgenai
from .genai_api import api_key as genai_api_key
import json

# ===============================
# Базовая конфигурация LLM
# ===============================
oldgenai.configure(api_key=genai_api_key)

def get_genai_modals():
    """Выводит список всех доступных моделей"""
    models = oldgenai.list_models()
    print("Доступные модели:")
    for model in models:
        print(f"- Имя: {model.name}")
        print(f"  Описание: {model.description}")
        print(f"  Поддерживаемые возможности: {model.supported_generation_methods}")
        print("-" * 20)


def generate_response(model_names: list, prompt: str) -> str:
    """
    Запрашивает модели из списка последовательно и возвращает ответ от первой успешно сработавшей модели.
    :param model_names: Список названий моделей (например, ['gemini-2.5-flash'])
    :param prompt: Текст запроса.
    :return: Строка ответа LLM в текстовом виде.
    """
    for model_name in model_names:
        try:
            model = oldgenai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Ошибка при запросе к модели {model_name}: {e}")
    print("Не удалось получить ответ ни от одной из указанных моделей.")
    return ''


def _process_json_response(json_string: str, key: str):
    """
    Универсальный парсер JSON ответа LLM.
    :param json_string: JSON-строка от LLM
    :param key: ключ верхнего уровня (например "questions", "summary", ...)
    :return: содержимое ключа либо None/[].
    """
    text = json_string.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        data = json.loads(text)
        if key in data:
            return data[key]
        else:
            print(f"Ошибка: ключ '{key}' не найден в ответе LLM.")
            return [] if isinstance(data, dict) else None
    except json.JSONDecodeError as e:
        print(f"Ошибка при парсинге JSON: {e}\nОтвет LLM: {text}")
        return [] if key == "questions" else None

# ----------------------------------------------------
# ФУНКЦИИ ДЛЯ РАЗЛИЧНЫХ AI-ЗАДАЧ
# ----------------------------------------------------

MODEL_NAMES = ['gemini-2.5-flash','gemini-2.5-flash-lite','gemini-2.0-flash-lite']


def generate_questions(topic: str, n: int = 10) -> list:
    """
    Генерация открытых вопросов по теме.
    Возвращает список вопросов.
    """
    prompt = (
        f"Ты — эксперт по проведению социологических опросов.\n"
        f"Сгенерируй {n} ОТКРЫТЫХ вопросов по теме: «{topic}».\n"
        f"Каждый вопрос должен:\n"
        f"  • стимулировать развёрнутый ответ,\n"
        f"  • избегать наводящих формулировок,\n"
        f"  • быть релевантным теме.\n"
        f"Верни в ЧИСТОМ JSON:\n"
        f'{{"questions": ["Вопрос 1", "Вопрос 2", ...]}}'
    )
    response = generate_response(MODEL_NAMES, prompt)
    return _process_json_response(response, "questions")


def summarize_text(answers: list) -> str:
    """
    Суммаризация множества ответов.
    Возвращает общий объединённый ответ, отражающий основные идеи большинства респондентов.
    """
    answers_text = json.dumps(answers, ensure_ascii=False)
    prompt = (
        "Ты — аналитик социологических данных.\n"
        "Проанализируй список текстовых ответов респондентов.\n"
        "Составь ОДИН объединённый краткий ответ, который отражает общее мнение большинства.\n"
        "Верни результат в ЧИСТОМ JSON:\n"
        '{"summary": "<объединённое резюме>"}\n'
        f"Список ответов: {answers_text}"
    )
    response = generate_response(MODEL_NAMES, prompt)
    return _process_json_response(response, "summary")


def evaluate_reliability(answers: list) -> list:
    """
    Оценка достоверности большого количества ответов.
    Возвращает массив из 0 и 1 (0 — сомнительный ответ, 1 — достоверный).
    """
    answers_text = json.dumps(answers, ensure_ascii=False)
    prompt = (
        "Ты — эксперт по анализу достоверности текстовых ответов.\n"
        "Для каждого ответа оцени: 1 — ответ выглядит достоверным, 0 — ответ сомнителен или явно ложный.\n"
        "Верни результат в ЧИСТОМ JSON формате:\n"
        '{"reliability": [0 или 1 для каждого ответа, в том же порядке]}\n'
        f"Список ответов: {answers_text}"
    )
    response = generate_response(MODEL_NAMES, prompt)
    return _process_json_response(response, "reliability")


def detect_anomalies(question: str, answers: list) -> list:
    """
    Выявление аномальных или сомнительных ответов с учётом самого вопроса.
    Возвращает массив индексов аномальных ответов.
    """
    answers_text = json.dumps(answers, ensure_ascii=False)
    prompt = (
        "Ты — аналитик аномалий в социологических исследованиях.\n"
        "Дан вопрос и список ответов.\n"
        "Найди ответы, которые явно не соответствуют вопросу или выглядят аномальными.\n"
        "Верни индексы этих ответов в ЧИСТОМ JSON:\n"
        '{"anomalies": [список индексов]}\n'
        f"Вопрос: {question}\n"
        f"Список ответов: {answers_text}"
    )
    response = generate_response(MODEL_NAMES, prompt)
    return _process_json_response(response, "anomalies")


def check_question_bias(questions: list) -> list:
    """
    Проверка списка вопросов на наличие формулировок,
    стимулирующих пользователя давать социально-желательные или ложные ответы.
    Например: «знаете ли вы», «знаком ли вам».
    Возвращает список индексов вопросов, которые рекомендуется переформулировать.
    """
    questions_text = json.dumps(questions, ensure_ascii=False)
    prompt = (
        "Ты — специалист по дизайну анкет.\n"
        "Проанализируй список вопросов и укажи индексы тех, которые могут провоцировать респондентов "
        "давать социально-желательные ответы (например, фразы «знаете ли вы», «знаком ли вам») "
        "или вопрос не имеет никакого смысла.\n"
        "Верни в ЧИСТОМ JSON формате:\n"
        '{"biased_questions": [список индексов таких вопросов]}\n'
        f"Список вопросов: {questions_text}"
    )
    response = generate_response(MODEL_NAMES, prompt)
    return _process_json_response(response, "biased_questions")


# ------------------------------
# Пример использования
# ------------------------------
if __name__ == "__main__":
    # 1. Генерация вопросов
    qs = generate_questions("Доставка еды", 5)
    print("Сгенерированные вопросы:", qs)

    # 2. Суммаризация множества ответов
    answers_example = ["Мне нравится быстрая доставка.", "Хочу больше вариантов оплаты."]
    summary = summarize_text(answers_example)
    print("Объединённый ответ:", summary)

    # 3. Оценка достоверности множества ответов
    reliability = evaluate_reliability(["Я летаю на Марс", "Мне нравится пицца"])
    print("Оценка достоверности (0/1):", reliability)

    # 4. Поиск аномалий (с вопросом)
    anomalies = detect_anomalies("Что вам нравится в нашей доставке?", answers_example)
    print("Аномальные ответы:", anomalies)

    # 5. Проверка вопросов на предвзятость
    bias = check_question_bias(["Знаете ли вы про наш сервис?", "Что улучшить в работе?"])
    print("Вопросы, требующие переформулировки:", bias)
