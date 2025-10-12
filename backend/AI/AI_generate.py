from openai import OpenAI
import google.generativeai as oldgenai
from .genai_api import api_key as genai_api_key
import json
import random

PROXY_URL = "https://gemini-proxy.ashutkin.workers.dev/v1"
API_KEY = genai_api_key

# ===============================
# КЛИЕНТ
# ===============================
client = OpenAI(
    api_key=API_KEY,  # Передаем ключ здесь
    base_url=PROXY_URL
)

# ===============================
# ФУНКЦИИ
# ===============================

def get_available_models():
    """Получает список доступных моделей через прокси"""
    try:
        models = client.models.list()
        print("Доступные модели:")
        for model in models.data:
            print(f"- {model.id}")
        return models.data
    except Exception as e:
        print(f"Ошибка при получении моделей: {e}")
        return []

def generate_response(model_name: str, prompt: str) -> str:
    """
    Отправляет запрос к Gemini через прокси
    :param model_name: Имя модели (например 'gemini-pro')
    :param prompt: Текст запроса
    :return: Ответ модели
    """
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка при запросе: {e}")
        return ""


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


def generate_questions_repeat(topic: str, n: int = 10) -> list:
    """
    Генерация пар вопросов по теме (разные формулировки, один смысл).
    Возвращает случайно перемешанный список вопросов.
    """
    prompt = (
        f"Ты — эксперт по проведению социологических опросов.\n"
        f"Сгенерируй {n} пар ОТКРЫТЫХ вопросов по теме: «{topic}».\n"
        f"Каждая пара должна содержать два вопроса с ОДИНАКОВЫМ смыслом, "
        f"но с разной формулировкой.\n"
        f"Избегай наводящих и неестественных фраз.\n"
        f"Верни результат в ЧИСТОМ JSON:\n"
        f'{{"questions": [{{"pair": ["вопрос_1", "вопрос_2"]}}, ...]}}'
    )

    response = generate_response(MODEL_NAMES, prompt)
    pairs = _process_json_response(response, "questions")

    if not pairs:
        return []

    # ✅ Перемешиваем все вопросы
    all_questions = [q for pair in pairs for q in pair.get("pair", [])]
    random.shuffle(all_questions)
    return all_questions

def evaluate_answer_quality(questions: list, answers: list) -> dict:
    """
    Проверяет качество ответов.
    Возвращает JSON:
    {
        "evaluations": [{"question": str, "answer": str, "score": float, "issues": [str]}],
        "overall_score": float
    }
    """
    questions_text = json.dumps(questions, ensure_ascii=False)
    answers_text = json.dumps(answers, ensure_ascii=False)

    prompt = (
        "Ты — эксперт по когнитивному анализу ответов респондентов.\n"
        "Проанализируй соответствие ответов вопросам, их логическую связность и внутренние противоречия.\n"
        "Для каждого вопроса оцени:\n"
        "- точность и осмысленность (0–1),\n"
        "- укажи кратко, какие проблемы (если есть).\n"
        "Также вычисли общую оценку качества (overall_score) — среднее по всем ответам.\n"
        "Верни в ЧИСТОМ JSON виде:\n"
        "{\n"
        '  "evaluations": [\n'
        '    {"question": "<текст>", "answer": "<текст>", "score": 0.0–1.0, "issues": ["строка1", "строка2"]}, ...\n'
        '  ],\n'
        '  "overall_score": 0.0–1.0\n'
        "}"
        f"\n\nВопросы: {questions_text}\nОтветы: {answers_text}"
    )

    try:
        response = client.chat.completions.create(
            model=random.choice(MODEL_NAMES),
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)

        # ✅ Автоматический перерасчёт average_score, если нет overall_score
        scores = [e.get("score", 0) for e in data.get("evaluations", [])]
        if not scores:
            print("⚠️ Нет индивидуальных оценок, устанавливается 0.0")
            avg = 0.0
        else:
            avg = round(sum(scores) / len(scores), 3)

        if "overall_score" not in data or data.get("overall_score") is None:
            print(f"ℹ️ overall_score не найден — пересчитан вручную: {avg}")
            data["overall_score"] = avg
        else:
            print(f"✅ overall_score из LLM: {data['overall_score']}")

        print(f"🧾 Средний расчёт (average_score): {avg}")
        return data

    except Exception as e:
        print(f"Ошибка анализа качества: {e}")
        return {"evaluations": [], "overall_score": 0.0}

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
        "Найди ответы, которые явно не соответствуют вопросу или точно аномальные.\n"
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
