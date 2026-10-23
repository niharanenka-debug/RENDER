from typing import Any

from pydantic import BaseModel, Field, field_validator


class Question(BaseModel):
    question: str
    options: dict[str, str]
    correct_answer: str
    explanation: str
    hint: str | None = None
    topic: str = "General"
    difficulty: str = "Medium"
    source_ref: str = ""

    @field_validator("correct_answer")
    @classmethod
    def valid_answer(cls, value):
        if value not in "ABCD":
            raise ValueError("correct_answer must be A, B, C, or D")
        return value

    @field_validator("options")
    @classmethod
    def four_options(cls, value):
        if set(value) != set("ABCD"):
            raise ValueError("options must contain A-D")
        return value


class QuizPayload(BaseModel):
    questions: list[Question] = Field(min_length=1, max_length=25)

    @field_validator("questions")
    @classmethod
    def no_dupes(cls, value):
        if len({question.question.strip().lower() for question in value}) != len(value):
            raise ValueError("duplicate questions")
        return value


class Flashcard(BaseModel):
    front: str
    back: str
    rating: str = "Needs Review"
    source_ref: str = ""

    @field_validator("rating")
    @classmethod
    def valid_rating(cls, value):
        if value not in {"Again", "Hard", "Good", "Easy", "Needs Review", "Difficult"}:
            raise ValueError("rating must be Again, Hard, Good, or Easy")
        return value
