import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Topic, Step, QuizQuestion, SelftestAttempt

app = FastAPI(title="Microlearning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities
class TopicCreate(BaseModel):
    title: str
    description: str
    tags: List[str] = []
    estimated_minutes: int = 10
    steps: List[Step] = []


def to_obj_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


@app.get("/")
def root():
    return {"message": "Microlearning API is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or "Unknown"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    return response


# ------------------ Topics ------------------
@app.post("/api/topics", response_model=dict)
def create_topic(payload: TopicCreate):
    topic = Topic(**payload.model_dump())
    topic_id = create_document("topic", topic)
    return {"id": topic_id}


@app.get("/api/topics", response_model=List[dict])
def list_topics(tag: Optional[str] = None):
    query = {"tags": {"$in": [tag]}} if tag else {}
    items = get_documents("topic", query)
    # serialize
    result = []
    for it in items:
        it["id"] = str(it.pop("_id"))
        # keep only summary fields in list view
        result.append({
            "id": it["id"],
            "title": it.get("title"),
            "description": it.get("description"),
            "tags": it.get("tags", []),
            "estimated_minutes": it.get("estimated_minutes", 10),
            "steps_count": len(it.get("steps", []))
        })
    return result


@app.get("/api/topics/{topic_id}", response_model=dict)
def get_topic(topic_id: str):
    doc = db["topic"].find_one({"_id": to_obj_id(topic_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Topic not found")
    doc["id"] = str(doc.pop("_id"))
    return doc


# ------------------ Self-test & Quiz ------------------
class SubmitAnswers(BaseModel):
    topic_id: str
    answers: List[int]  # index of chosen options in order of quiz questions encountered


@app.post("/api/selftest/submit", response_model=dict)
def submit_selftest(payload: SubmitAnswers):
    topic = db["topic"].find_one({"_id": to_obj_id(payload.topic_id)})
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # collect questions in order from steps with type 'quiz'
    questions: List[dict] = []
    for step in topic.get("steps", []):
        if step.get("type") == "quiz":
            for q in step.get("quiz_questions", []) or []:
                questions.append(q)

    if not questions:
        raise HTTPException(status_code=400, detail="No quiz questions in this topic")

    total = len(questions)
    correct = 0
    detailed = []

    for i, q in enumerate(questions):
        chosen = payload.answers[i] if i < len(payload.answers) else None
        is_correct = (chosen == q.get("correct_index"))
        correct += 1 if is_correct else 0
        detailed.append({
            "question": q.get("question"),
            "chosen": chosen,
            "correct_index": q.get("correct_index"),
            "is_correct": is_correct,
            "hots_level": q.get("hots_level", "understand"),
            "explanation": q.get("explanation")
        })

    score = round((correct / total) * 100, 2)

    attempt = SelftestAttempt(
        topic_id=payload.topic_id,
        score=score,
        total_questions=total,
        answers=detailed,
    )
    attempt_id = create_document("selftestattempt", attempt)

    return {"attempt_id": attempt_id, "score": score, "correct": correct, "total": total, "details": detailed}


# Seed endpoint to create a sample topic for demo
@app.post("/api/seed", response_model=dict)
def seed_sample():
    sample = Topic(
        title="Dasar Pemrograman Python",
        description="Microlearning bertahap: teori, studi kasus, kuis HOTS, dan self-test.",
        tags=["programming", "python", "beginner"],
        estimated_minutes=25,
        steps=[
            Step(type="theory", title="Apa itu Variabel?", content="Variabel menyimpan nilai. Di Python, kita tidak perlu mendeklarasikan tipe."),
            Step(type="case", title="Studi Kasus: Hitung Rata-Rata", case_prompt="Diberikan list nilai ujian, hitung rata-rata dan kategorikan lulus/tidak."),
            Step(
                type="quiz",
                title="Kuis HOTS 1",
                quiz_questions=[
                    QuizQuestion(
                        question="Apa output dari: x=\"2\"; y=3; print(x*y)?",
                        options=["6", "222", "23", "Error"],
                        correct_index=1,
                        hots_level="apply",
                        explanation="String '2' dikali 3 menjadi '222' di Python."
                    ),
                    QuizQuestion(
                        question="Manakah yang paling tepat untuk menghindari bug saat membandingkan floating point?",
                        options=[
                            "Gunakan == langsung",
                            "Gunakan pembulatan ke 2 desimal dulu",
                            "Gunakan toleransi (epsilon) saat membandingkan",
                            "Konversi ke int sebelum membandingkan"
                        ],
                        correct_index=2,
                        hots_level="analyze",
                        explanation="Perbandingan float sebaiknya menggunakan toleransi kesalahan."
                    ),
                ]
            ),
            Step(type="selftest", title="Self-Test: Cek Pemahaman", content="Jawab semua pertanyaan kuis kemudian lihat skor Anda."),
        ]
    )
    new_id = create_document("topic", sample)
    return {"id": new_id}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
