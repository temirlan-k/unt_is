from datetime import datetime
import json
from typing import List
from beanie import PydanticObjectId
from src.models.question import Question
from src.models.user import User
from src.models.mistake_bank import MistakeBankQuiz
from src.schemas.req.generated_quiz import UserAnswerRequest
from src.models.generated_quiz import GeneratedQuiz, GeneratedQuestion, QuestionOption, UserAnswer, UserGeneratedQuizAttempt
from src.helpers.llm import LLMClient
from fastapi import HTTPException

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from bson import ObjectId


class QuizGeneratorService:

    async def generate_quiz(self, user_prompt: str, user_id:PydanticObjectId) -> GeneratedQuiz:
        llm_client = LLMClient()
            
        response = await llm_client.generate_response(user_prompt)

        quiz_data = json.loads(response)

        questions = [
            GeneratedQuestion(
                id=PydanticObjectId(),
                type=question_data["type"],
                question_text=question_data["question_text"],
                options=[QuestionOption(**option) for option in question_data["options"]]
            )
            for question_data in quiz_data["questions"]
        ]
        generated_quiz = GeneratedQuiz(
            user_id=user_id, 
            title=quiz_data["title"],
            subject=quiz_data["subject"],
            questions=questions
        )
        await generated_quiz.insert()

        return generated_quiz


    async def get_user_attempts(self, user_id: PydanticObjectId):
        """Возвращает список попыток пользователя с добавлением quiz_title и полной информации о вопросах"""
        attempts = await UserGeneratedQuizAttempt.find(UserGeneratedQuizAttempt.user_id == user_id).to_list()
        
        if not attempts:
            raise HTTPException(status_code=404, detail="No attempts found")

        # Собираем все quiz_id и question_id из попыток
        quiz_ids = {attempt.quiz_id for attempt in attempts}
        question_ids = {answer.question_id for attempt in attempts for answer in attempt.answers}

        # Загружаем все викторины
        quizzes = await GeneratedQuiz.find({"_id": {"$in": list(quiz_ids)}}).to_list()
        quiz_map = {quiz.id: quiz for quiz in quizzes}

        # Собираем все вопросы
        questions_map = {}
        for quiz in quizzes:
            for question in quiz.questions:
                questions_map[question.id] = question

        # Формируем респонс с полной инфой
        response = []
        for attempt in attempts:
            quiz = quiz_map.get(attempt.quiz_id)
            if not quiz:
                continue  # Пропускаем, если quiz_id не найден

            attempt_data = jsonable_encoder(attempt)
            attempt_data["id"] = str(attempt.id)
            attempt_data["user_id"] = str(attempt.user_id)
            attempt_data["quiz_id"] = str(attempt.quiz_id)
            attempt_data["quiz_title"] = quiz.title
            attempt_data["quiz_subject"] = quiz.subject

            # Добавляем полные данные о вопросах
            for answer in attempt_data["answers"]:
                question = questions_map.get(ObjectId(answer["question_id"]))
                if question:
                    answer["question_id"] = str(answer["question_id"])
                    answer["question_text"] = question.question_text
                    answer["options"] = [
                        {"label": option.label, "text": option.option_text, "is_correct": option.is_correct}
                        for option in question.options
                    ]

            response.append(attempt_data)

        return response


    async def get_all_quizzes(self):
        return await GeneratedQuiz.find_all().to_list()
    
    async def get_quizzes_by_user(self, user_id: PydanticObjectId):
        return await GeneratedQuiz.find(GeneratedQuiz.user_id == user_id).to_list()
    
    async def start_quiz_attempt(self, user_id: PydanticObjectId, quiz_id: PydanticObjectId):
        attempt = UserGeneratedQuizAttempt(
            user_id=user_id,
            quiz_id=quiz_id,
            started_at=datetime.utcnow()
        )
        await attempt.insert()
        return attempt
    
    async def submit_quiz_attempt(self, attempt_id: PydanticObjectId):
        """Завершает попытку квиза, суммирует баллы и обновляет счет пользователя."""
        attempt = await UserGeneratedQuizAttempt.get(attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found")

        if attempt.finished_at:
            raise HTTPException(status_code=400, detail="Attempt already finished")

        # Считаем общий балл на основе уже данных ответов
        total_score = sum(ans.score for ans in attempt.answers)

        # Фиксируем завершение попытки
        attempt.score = total_score
        attempt.finished_at = datetime.utcnow()
        await attempt.save()

        # Обновляем общий счет пользователя
        user = await User.get(attempt.user_id)
        if user:
            user.total_score += total_score
            await user.save()

        return {"message": "Quiz attempt submitted", "total_score": total_score}

    
    async def answer_question(
        self, 
        attempt_id: PydanticObjectId, 
        answer: UserAnswerRequest
    ):
        """Добавляет ответ на вопрос в текущую попытку"""
        attempt = await UserGeneratedQuizAttempt.get(attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found")

        if attempt.finished_at:
            raise HTTPException(status_code=400, detail="Attempt already finished")

        quiz = await GeneratedQuiz.get(attempt.quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        question = next((q for q in quiz.questions if q.id == answer.question_id), None)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        # Проверка, был ли уже дан ответ на этот вопрос в текущей попытке
        if any(ans.question_id == answer.question_id for ans in attempt.answers):
            raise HTTPException(status_code=400, detail="Question already answered in this attempt")

        # Подсчет баллов
        correct_options = {opt.label for opt in question.options if opt.is_correct}
        selected_options = set(answer.selected_options)

        selected_correct = len(selected_options & correct_options)
        total_correct = len(correct_options)

        score = 0
        if question.type == "single_choice":
            score = 1 if selected_correct == 1 else 0
        elif question.type == "multiple_choice":
            if selected_options == correct_options:  # Полностью правильный ответ
                score = 2
            elif selected_correct > 0 and selected_options.issubset(correct_options):  # Частично правильный без ошибок
                score = 1
            else:  # Если есть хотя бы одна ошибка
                score = 0

        user_answer = UserAnswer(
            question_id=answer.question_id,
            selected_options=answer.selected_options,
            score=score
        )
        print(user_answer.question_id)
        if score == 0:
            mistake = MistakeBankQuiz(
                user_id=attempt.user_id,
                question_id=answer.question_id,
                added_at=datetime.utcnow(),
                quiz_id=quiz.id,  
                question_text=question.question_text, 
                options=[{"label": opt.label,"option_text":opt.option_text,'is_correct':opt.is_correct} for opt in question.options]   # Add options here
            )
            await mistake.insert()


    
        if attempt.score is None:
            attempt.score = 0
        attempt.answers.append(user_answer)
        attempt.score += score

        await attempt.save()
        return {"message": "Answer submitted", "score": score}
