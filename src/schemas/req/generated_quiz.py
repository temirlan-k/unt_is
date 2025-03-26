from typing import List
from beanie import PydanticObjectId
from pydantic import BaseModel


class QuizGenerationRequest(BaseModel):
    user_prompt: str
    question_types: List[str] = ['single_choice']

class UserAnswerRequest(BaseModel):
    question_id: PydanticObjectId
    selected_options: List[str]  # Выбранные варианты (например, ["A", "C"])

class BulkUserAnswerRequest(BaseModel):
    answers: List[UserAnswerRequest]
