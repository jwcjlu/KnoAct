from fastapi import FastAPI
from .routers import auth, config_router, pdf, progress, notes, points

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
