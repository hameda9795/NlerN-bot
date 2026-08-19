"""Dormant REST endpoints for the reusable question bank.

When eventually mounted on the membership FastAPI app, two endpoints back the
dynamic Q&A flow:

* ``GET  /api/questions/next``   — next unseen approved question + its 4 options
* ``POST /api/questions/answer`` — grade an answer, store it, update progress

This router is intentionally not mounted by ``webapp.main`` until a real
consumer and Telegram WebApp ``initData`` authentication are implemented.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.question_selection_service import QuestionSelectionService
from services.question_service import (
    NO_UNSEEN_QUESTION_AVAILABLE,
    QuestionView,
    record_answer,
    user_exists,
)

router = APIRouter(prefix="/api/questions", tags=["questions"])
_selection = QuestionSelectionService()


class AnswerRequest(BaseModel):
    user_id: int = Field(..., alias="userId")
    question_id: int = Field(..., alias="questionId")
    selected_option_key: str = Field(..., alias="selectedOptionKey")
    time_spent_seconds: int | None = Field(default=None, alias="timeSpentSeconds")

    model_config = {"populate_by_name": True}


@router.get("/next")
async def next_question(
    userId: int = Query(...),
    level: str = Query(...),
    section: str = Query(...),
    topic: str = Query(...),
) -> dict:
    """Return the next unseen approved question for this user, or a clear status."""
    if not await user_exists(user_id=userId):
        raise HTTPException(status_code=400, detail="USER_NOT_FOUND")
    result = await _selection.get_next_question(
        user_id=userId, level=level, section=section, topic=topic
    )
    if isinstance(result, QuestionView):
        return {"status": "OK", "question": asdict(result)}
    # Sentinel string — bucket exhausted for this user; do not generate yet.
    return {"status": result, "question": None}


@router.post("/answer")
async def answer_question(payload: AnswerRequest) -> dict:
    """Grade the answer, persist the attempt and update progress."""
    if not await user_exists(user_id=payload.user_id):
        raise HTTPException(status_code=400, detail="USER_NOT_FOUND")
    result = await record_answer(
        user_id=payload.user_id,
        question_id=payload.question_id,
        selected_option_key=payload.selected_option_key,
        time_spent_seconds=payload.time_spent_seconds,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="QUESTION_NOT_FOUND")
    return {"status": "OK", "result": asdict(result)}
