from fastapi import FastAPI

app = FastAPI(title="知学伴 API")

@app.get("/health")
def health():
    return {"status": "ok"}
