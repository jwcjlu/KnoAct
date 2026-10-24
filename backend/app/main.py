from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, config_router, pdf, progress, notes, points, learning, goals, mistakes, knowledge, tts_router

app = FastAPI(title="知学伴 API")

# 开发阶段放开跨域，便于前端本地联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(tts_router.router)
