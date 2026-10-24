from fastapi import FastAPI
from .routers import auth, config_router, pdf, progress, notes, points, learning, goals, mistakes, knowledge

app = FastAPI(title="知学伴 API")

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(auth.router)
app.include_router(config_router.router)
app.include_router(pdf.router)
app.include_router(progress.router)
app.include_router(notes.router)
app.include_router(points.router)
app.include_router(learning.router)
app.include_router(goals.router)
app.include_router(mistakes.router)
app.include_router(knowledge.router)
