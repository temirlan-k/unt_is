from beanie import PydanticObjectId
from fastapi import HTTPException
from datetime import datetime
from src.schemas.res.question import OptionResponse, QuestionResponse
from src.models.user_answer import AnswerCreate, UserAnswer
from src.models.user import User
from src.models.quiz import Quiz, QuizStructure
from src.models.question import Question
from src.models.quiz_session import UserQuizAttempt
from src.schemas.req.quiz import QuizCreateDTO, QuestionDTO
from src.models.enums import QuizSubject, QuestionType
from src.models.mistake_bank import MistakeBankQuiz
from fastapi.encoders import jsonable_encoder

class QuizService:
    async def create_quiz(self, quiz_data: QuizCreateDTO):
        """Создание нового квиза"""
        quiz = Quiz(
            variant=quiz_data.variant,
            year=quiz_data.year,
            title=quiz_data.title,
        )        
        await quiz.insert()
        new_subjects = [
            QuizStructure(subject=sub.subject, question_count=sub.question_count)
            for sub in quiz_data.subjects  
        ]
        await quiz.add_subjects(new_subjects)  
        return quiz

    async def add_question(self, quiz_id: PydanticObjectId, question_data: QuestionDTO):
        """Добавление вопроса в квиз"""
        quiz = await Quiz.get(quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        question = Question(quiz_id=quiz_id, **question_data.dict())
        await question.insert()
        return question

    async def get_all_quizzes(self):
        """Получение всех квизов"""
        return await Quiz.find_all().to_list()

    async def start_quiz_attempt(self, quiz_id: PydanticObjectId, user_id: PydanticObjectId):
        """Начало попытки квиза"""
        attempt = UserQuizAttempt(user_id=user_id, quiz_id=quiz_id, score=0)
        await attempt.insert()
        return attempt

    async def submit_answer(self, attempt_id: PydanticObjectId, answer_data: AnswerCreate, user_id: PydanticObjectId):
        """Сохраняет ответ пользователя на вопрос и проверяет правильность"""
        attempt = await UserQuizAttempt.get(attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail='Quiz attempt not found')
        if attempt.user_id != user_id:
            raise HTTPException(status_code=403, detail="You can't rewrite someone's quiz attempt")
        
        # Проверка, что пользователь не отвечал на этот вопрос ранее
        existing_answer = await UserAnswer.find_one({"attempt_id": attempt_id, "question_id": answer_data.question_id})
        if existing_answer:
            raise HTTPException(status_code=400, detail="You have already answered this question")
        
        question = await Question.get(answer_data.question_id)
        if not question:
            raise HTTPException(status_code=404, detail='Question not found')
        
        score = 0
        
        if question.type == QuestionType.SINGLE_CHOICE:
            correct_option = next((opt for opt in question.options if opt.is_correct), None)
            score = 1 if correct_option and correct_option.label in answer_data.option_labels else 0
        
        elif question.type == QuestionType.MULTIPLE_CHOICE:
            correct_options = {opt.label for opt in question.options if opt.is_correct}
            selected_options = set(answer_data.option_labels)
            correct_selected = selected_options & correct_options
            
            if len(correct_selected) == len(correct_options):
                score = 2 
            elif len(correct_selected) > 0:
                score = 1  
            else:
                score = 0 
    
        user_answer = UserAnswer(
            attempt_id=attempt_id,
            question_id=answer_data.question_id,
            selected_options=answer_data.option_labels,
            score=score,
        )
        await user_answer.insert()

        return user_answer
    
    async def submit_quiz_attempt(self, attempt_id: PydanticObjectId, user_id: PydanticObjectId):
        """Завершение квиза с автоматическим расчетом балла"""
        attempt = await UserQuizAttempt.get(attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="Quiz Attempt not found")
        if attempt.user_id != user_id:
            raise HTTPException(status_code=403, detail="You can't submit someone else's quiz attempt")

        user_answers = await UserAnswer.find({"attempt_id": attempt_id}).to_list()
        total_score = sum(answer.score for answer in user_answers)
        attempt.score = total_score
        attempt.ended_at = datetime.utcnow()
        attempt.is_completed = True

        user = await User.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.total_score = (user.total_score or 0) + total_score
        
        await attempt.save()
        await user.save()
        
        return {
            "attempt_id": str(attempt.id),
            "quiz_id": str(attempt.quiz_id),
            "total_score": total_score,
        }
    
    async def get_quiz_questions(self, quiz_id: PydanticObjectId):
        """Получить список вопросов для квиза"""
        questions = await Question.find(
            {"quiz_id": quiz_id,}  
        ).to_list()
        
        return [
            QuestionResponse(
                id=str(q.id),
                quiz_id=str(q.quiz_id),
                type=q.type,
                subject=q.subject,
                question_text=q.question_text,
                options=[
                    OptionResponse(label=o.label, option_text=o.option_text) 
                    for o in q.options
                ]
            )
            for q in questions
        ]


    async def get_user_quiz_attempts(self, user_id: PydanticObjectId):
        """Возвращает список попыток пользователя с полной информацией о квизах и вопросах."""
        attempts = await UserQuizAttempt.find({"user_id": user_id}).to_list()
        if not attempts:
            raise HTTPException(status_code=404, detail="No attempts found")
        
        # Собираем все quiz_id и question_id
        quiz_ids = {attempt.quiz_id for attempt in attempts}
        attempt_ids = {attempt.id for attempt in attempts}
        user_answers = await UserAnswer.find({"attempt_id": {"$in": list(attempt_ids)}}).to_list()
        question_ids = {answer.question_id for answer in user_answers}
        
        # Загружаем все квизы и вопросы
        quizzes = await Quiz.find({"_id": {"$in": list(quiz_ids)}}).to_list()
        questions = await Question.find({"_id": {"$in": list(question_ids)}}).to_list()
        
        quiz_map = {quiz.id: quiz for quiz in quizzes}
        question_map = {question.id: question for question in questions}
        
        response = []
        for attempt in attempts:
            quiz = quiz_map.get(attempt.quiz_id)
            if not quiz:
                continue  # Пропускаем, если квиз не найден
            
            # Преобразуем ObjectId в строку
            attempt_data = jsonable_encoder(attempt)
            attempt_data["id"] = str(attempt.id)
            attempt_data["quiz_id"] = str(attempt.quiz_id)
            attempt_data["user_id"] = str(attempt.user_id)

            attempt_data["quiz_title"] = quiz.title
            attempt_data["quiz_variant"] = quiz.variant
            attempt_data["quiz_year"] = quiz.year

            # Добавляем детали ответов
            attempt_data["answers"] = []
            for answer in user_answers:
                if answer.attempt_id == attempt.id:
                    question = question_map.get(answer.question_id)
                    if question:
                        attempt_data["answers"].append({
                            "question_text": question.question_text,
                            "selected_options": answer.selected_options,
                            "options": [
                                {
                                    "label": opt.label,
                                    "text": opt.option_text,
                                    "is_correct": opt.is_correct
                                }
                                for opt in question.options
                            ]
                        })

            response.append(attempt_data)
        
        return response



    async def get_detailed_answers(self, attempt_id: PydanticObjectId, user_id: PydanticObjectId):
        attempt = await UserQuizAttempt.get(attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="Quiz attempt not found")
        if attempt.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        user_answers = await UserAnswer.find({"attempt_id": attempt_id}).to_list()
        question_list = await Question.find({"_id": {"$in": [ua.question_id for ua in user_answers]}}).to_list()

        return question_list


    async def get_attempt_details(self, attempt_id: PydanticObjectId, user_id: PydanticObjectId):
        """Возвращает подробную информацию о конкретной попытке пользователя."""
        attempt = await UserQuizAttempt.get(attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="Quiz attempt not found")
        if attempt.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Загружаем ответы пользователя на этот квиз
        user_answers = await UserAnswer.find({"attempt_id": attempt_id}).to_list()
        question_ids = [ua.question_id for ua in user_answers]
        
        # Загружаем вопросы и сам квиз
        questions = await Question.find({"_id": {"$in": question_ids}}).to_list()
        quiz = await Quiz.get(attempt.quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        # Преобразуем вопросы в удобный формат
        question_map = {q.id: q for q in questions}

        # Формируем ответ
        response = {
            "attempt_id": str(attempt.id),
            "quiz_id": str(attempt.quiz_id),
            "user_id": str(attempt.user_id),
            "quiz_title": quiz.title,
            "quiz_variant": quiz.variant,
            "quiz_year": quiz.year,
            "answers": []
        }

        for ua in user_answers:
            question = question_map.get(ua.question_id)
            if question:
                response["answers"].append({
                    "question_id": str(question.id),
                    "question_text": question.question_text,
                    "options": [
                        {
                            "label": opt.label,
                            "option_text": opt.option_text,
                            "is_correct": opt.is_correct
                        }
                        for opt in question.options
                    ],
                    "selected_option": ua.selected_options  # Добавляем выбор пользователя
                })

        return response
