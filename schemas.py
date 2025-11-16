"""
Database Schemas for Microlearning App

Each Pydantic model represents a collection in MongoDB. The collection name is the lowercase of the class name.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

HOTSLevel = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]

class QuizQuestion(BaseModel):
    id: Optional[str] = Field(None, description="Client-friendly id for the question")
    question: str
    options: List[str]
    correct_index: int = Field(..., ge=0, description="Index of the correct option")
    hots_level: HOTSLevel = Field("understand", description="Cognitive level based on Bloom's taxonomy")
    explanation: Optional[str] = Field(None, description="Explanation for the correct answer")

class Step(BaseModel):
    type: Literal["theory", "case", "quiz", "selftest"]
    title: str
    content: Optional[str] = Field(None, description="Markdown/HTML content for theory/case steps")
    case_prompt: Optional[str] = Field(None, description="Prompt/Scenario for case study")
    quiz_questions: Optional[List[QuizQuestion]] = Field(None, description="Questions for quiz step")

class Topic(BaseModel):
    title: str
    description: str
    tags: List[str] = []
    estimated_minutes: int = 10
    steps: List[Step] = Field(default_factory=list)

class SelftestAttempt(BaseModel):
    topic_id: str
    score: float
    total_questions: int
    answers: List[dict] = Field(default_factory=list, description="List of user answers and correctness per question")
    user_id: Optional[str] = None
