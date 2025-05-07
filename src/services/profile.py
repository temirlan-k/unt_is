import re
from beanie import Link, PydanticObjectId
from bson import ObjectId
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from src.models.generated_quiz import GeneratedQuiz, UserGeneratedQuizAttempt
from src.helpers.jwt_handler import JWT
from src.helpers.password import PasswordHandler
from src.models.user import  User
from src.schemas.req.profile import  QuizStats, UserProfileUpdateReq
from src.schemas.req.user import UserCreateReq, UserLoginReq


class ProfileService:

    async def get_user_by_id(self, user_id: str):
        user = await User.find_one(User.id == PydanticObjectId(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "score":user.total_score,
            "role":user.role,
            "avatar":user.avatar
        }

    async def update_profile(self, user_id: str, profile_data: UserProfileUpdateReq):
        user = await User.find_one(User.id == PydanticObjectId(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if profile_data.first_name is not None:
            user.first_name = profile_data.first_name
        if profile_data.last_name is not None:
            user.last_name = profile_data.last_name
        if profile_data.email is not None:
            user.email = profile_data.email
        if profile_data.password is not None:
            user.password = PasswordHandler.hash(profile_data.password)

        await user.save()
        return user

    async def get_leaderboard(self, search: str, skip: int = 0, limit: int = 10):
        """Возвращает топ пользователей по total_score с поддержкой пагинации"""
        query = {}

        if search:
            regex = {"$regex":re.escape(search), "$options":"i"}
            query = {
                "$or": [
                    {"first_name": regex},
                    {"last_name": regex},
                    {"email": regex}
                ]
            }

        users = await User.find(query).sort("-total_score").skip(skip).limit(limit).to_list()
        total_users = await User.find(query).count()
        return {'users': users, "users_count": total_users} 

    async def get_user_rank(self, user_id: str):
        """Возвращает место текущего пользователя в лидерборде и его total_score"""
        user = await User.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        rank = await User.find(User.total_score > user.total_score).count() + 1
        total_users = await User.count()

        return {"rank": rank, "total_score": user.total_score, "users_count": total_users}
    
    
    async def get_quiz_stats(self, user_id: PydanticObjectId):
        # Получаем все сгенерированные квизы для данного пользователя
        generated_quizzes = await GeneratedQuiz.find(GeneratedQuiz.user_id == user_id).to_list()
        total_quizzes_generated = len(generated_quizzes)

        # Получаем все попытки прохождения квизов для данного пользователя
        quiz_attempts = await UserGeneratedQuizAttempt.find(UserGeneratedQuizAttempt.user_id == user_id).to_list()
        total_quizzes_completed = len(quiz_attempts)

        correct_answers = 0
        incorrect_answers = 0

        # Подсчитываем правильные и неправильные ответы, используя score из UserGeneratedQuizAttempt
        for attempt in quiz_attempts:
            for user_answer in attempt.answers:
                if user_answer.score > 0:
                    correct_answers += 1
                else:
                    incorrect_answers += 1

        # Рассчитываем процент успеха
        success_percentage = 0
        total_answers = correct_answers + incorrect_answers
        if total_answers > 0:
            success_percentage = (correct_answers / total_answers) * 100

        # Общий балл за все попытки
        total_score = sum(attempt.score for attempt in quiz_attempts)

        return QuizStats(
            total_quizzes_generated=total_quizzes_generated,
            total_quizzes_completed=total_quizzes_completed,
            correct_answers=correct_answers,
            incorrect_answers=incorrect_answers,
            success_percentage=success_percentage,
            total_score=total_score
        )