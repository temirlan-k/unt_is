from typing import Optional

from pydantic import BaseModel, EmailStr, constr


class UserProfileUpdateReq(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[constr(min_length=6)] = None


class QuizStats(BaseModel):
    total_quizzes_generated: int
    total_quizzes_completed: int
    correct_answers: int
    incorrect_answers: int
    success_percentage: float
