import unittest
import json
from .AI_generate import (
    generate_questions,
    summarize_text,
    evaluate_reliability,
    detect_anomalies,
    check_question_bias,
    evaluate_answer_quality,
    generate_questions_repeat
)


class AIFunctionsTest(unittest.TestCase):
    """Тестирование функций модуля AI-инструментов с детализированным выводом"""

    def _divider(self, title: str):
        print("\n" + "═" * 70)
        print(f"🧪 {title}")
        print("═" * 70)

    def test_generate_questions(self):
        self._divider("Тест: Генерация вопросов по теме")
        topic = "Доставка еды"
        qs = generate_questions(topic, 3)
        self.assertIsInstance(qs, list)
        print(f"📥 Тема: {topic}")
        print(f"📤 Сгенерировано {len(qs)} вопросов.")
        for i, q in enumerate(qs, start=1):
            print(f"  {i}. {q}")
        print("✅ Проверка структуры: список вопросов успешно получен.")

    def test_generate_questions_repeat(self):
        self._divider("Тест: Генерация вопросов по теме")
        topic = "Доставка еды"
        qs = generate_questions_repeat(topic, 3)
        self.assertIsInstance(qs, list)
        print(f"📥 Тема: {topic}")
        print(f"📤 Сгенерировано {len(qs)} вопросов.")
        for i, q in enumerate(qs, start=1):
            print(f"  {i}. {q}")
        print("✅ Проверка структуры: список вопросов успешно получен.")

    def test_summarize_text(self):
        self._divider("Тест: Суммаризация ответов")
        answers = ["Еда была вкусной", "Доставка быстрая", "Курьер вежлив"]
        summary = summarize_text(answers)
        self.assertIsInstance(summary, str)
        print(f"📥 Ответы ({len(answers)}): {answers}")
        print(f"📤 Суммаризация: {summary}")
        print("✅ Суммаризация успешно выполнена.")

    def test_evaluate_reliability(self):
        self._divider("Тест: Проверка достоверности ответов")
        answers = ["Мне нравится пицца", "Я живу на Солнце"]
        reliability = evaluate_reliability(answers)
        self.assertIsInstance(reliability, list)
        self.assertTrue(all(isinstance(x, int) for x in reliability))
        print(f"📥 Ответы: {answers}")
        print(f"📤 Результаты достоверности: {reliability}")
        print(f"🧩 Итог: {sum(reliability)} из {len(reliability)} признаны достоверными.")
        print("✅ Проверка достоверности успешно выполнена.")

    def test_detect_anomalies(self):
        self._divider("Тест: Обнаружение аномалий в ответах")
        question = "Что вам нравится в нашей доставке?"
        answers = ["Все хорошо", "Солнце горячее", "Курьер вежлив"]
        anomalies = detect_anomalies(question, answers)
        self.assertIsInstance(anomalies, list)
        print(f"📥 Вопрос: {question}")
        print(f"📥 Ответы: {answers}")
        print(f"📤 Аномальные индексы: {anomalies}")
        if anomalies:
            print(f"⚠️ Найдено {len(anomalies)} аномальных ответов.")
        else:
            print("✅ Аномалий не обнаружено.")
        print("🧩 Проверка завершена успешно.")

    def test_check_question_bias(self):
        self._divider("Тест: Проверка вопросов на предвзятость")
        questions = ["Знаете ли вы наш бренд?", "Что улучшить в сервисе?"]
        bias = check_question_bias(questions)
        self.assertIsInstance(bias, list)
        print(f"📥 Вопросы: {questions}")
        if bias:
            print(f"⚠️ Предвзятые вопросы (индексы): {bias}")
            for idx in bias:
                print(f"   • {idx}: {questions[idx]}")
        else:
            print("✅ Все вопросы нейтральны.")
        print("🧩 Проверка завершена успешно.")

    def test_evaluate_answer_quality_auto_score(self):
        self._divider("Тест: Автоматическая оценка качества ответов (average_score)")
        questions = ["Как вам доставка?", "Что улучшить?"]
        answers = ["Все отлично", "Добавьте новые блюда"]

        result = evaluate_answer_quality(questions, answers)
        self.assertIn("evaluations", result)
        self.assertIn("overall_score", result)
        self.assertIsInstance(result["overall_score"], float)

        print(f"📥 Вопросы: {questions}")
        print(f"📥 Ответы: {answers}")
        print("📊 Детализация по каждому ответу:")
        for i, ev in enumerate(result.get("evaluations", []), start=1):
            print(f"   {i}. Вопрос: {ev.get('question')}")
            print(f"      Ответ: {ev.get('answer')}")
            print(f"      Оценка: {ev.get('score')}")
            if ev.get("issues"):
                print(f"      ⚠️ Проблемы: {ev.get('issues')}")
        print(f"\n🧮 Итоговый расчёт качества (overall_score): {result['overall_score']}")
        print("✅ Тест оценки качества успешно завершён.")

    def test_full_example_scenario(self):
        self._divider("Тест: Полный сценарий работы модуля (__main__)")
        qs = generate_questions("Доставка еды", 2)
        summary = summarize_text(["Быстро", "Удобно"])
        reliability = evaluate_reliability(["Люблю еду", "Я робот"])
        anomalies = detect_anomalies("Что вам нравится?", ["Все", "Кошки летают"])
        bias = check_question_bias(["Знаете ли вы нас?", "Что улучшить?"])

        self.assertTrue(isinstance(qs, list))
        self.assertTrue(isinstance(summary, str))
        self.assertTrue(isinstance(reliability, list))
        self.assertTrue(isinstance(anomalies, list))
        self.assertTrue(isinstance(bias, list))

        print(f"📊 Вопросы ({len(qs)}): {qs}")
        print(f"📄 Суммаризация: {summary}")
        print(f"🧠 Надёжность ответов: {reliability}")
        print(f"🚨 Аномалии: {anomalies}")
        print(f"⚠️ Предвзятые вопросы: {bias}")
        print("✅ Полный сценарий прошёл успешно.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
