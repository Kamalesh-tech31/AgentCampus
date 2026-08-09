from fastapi import APIRouter
from app.contracts.students import StudentListResponse, ResetDbResponse
from app.services.student_service import student_service

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=StudentListResponse)
def get_students():
    students = student_service.get_students()
    return StudentListResponse(students=students, total=len(students))


@router.post("/reset", response_model=ResetDbResponse)
def reset_students():
    students = student_service.reset_db()
    return ResetDbResponse(message="Database reset successfully", students=students)
