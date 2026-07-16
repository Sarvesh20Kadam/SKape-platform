from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root():
    return {
        "product": "SKape OS",
        "status": "running",
        "version": "0.1.0"
    }