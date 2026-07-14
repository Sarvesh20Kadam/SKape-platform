from fastapi import FastAPI

app = FastAPI(
    title="SKape OS",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "product": "SKape OS",
        "status": "running",
        "version": "0.1.0"
    }
    