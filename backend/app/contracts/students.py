from typing import Literal, Optional, List
from pydantic import Field
from app.contracts.common import CamelModel

StudentDepartment = Literal[
    "Computer Science",
    "Electronics",
    "Mechanical",
    "Civil",
    "Data Science",
    "AI & ML",
]

StudentStatus = Literal["Active", "Probation", "Graduated"]


class StudentRecord(CamelModel):
    id: str
    roll_number: str
    name: str
    department: StudentDepartment
    cgpa: float = Field(..., ge=0.0, le=10.0)
    semester: int = Field(..., ge=1, le=8)
    attendance: float = Field(..., ge=0.0, le=100.0)
    email: str
    status: StudentStatus
    backlogs: int = Field(..., ge=0)
    project_title: Optional[str] = None


class StudentListResponse(CamelModel):
    students: List[StudentRecord]
    total: Optional[int] = None


class ResetDbResponse(CamelModel):
    message: str
    students: List[StudentRecord]
