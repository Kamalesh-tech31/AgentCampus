from typing import List
from app.contracts.students import StudentRecord, StudentDepartment
from app.db.student_queries import get_all_students
from app.db.student_mutations import delete_all_students, bulk_insert_students

INITIAL_STUDENT_DATA: List[dict] = [
    {
        "id": "STU-1001",
        "rollNumber": "21CS001",
        "name": "Aarav Sharma",
        "department": "Computer Science",
        "cgpa": 9.82,
        "semester": 8,
        "attendance": 96.0,
        "email": "aarav.sharma@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Distributed Agent Orchestration",
    },
    {
        "id": "STU-1002",
        "rollNumber": "21CS002",
        "name": "Ananya Roy",
        "department": "Computer Science",
        "cgpa": 9.65,
        "semester": 8,
        "attendance": 94.0,
        "email": "ananya.roy@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Neural LLM Compression",
    },
    {
        "id": "STU-1003",
        "rollNumber": "21CS003",
        "name": "Rohan Verma",
        "department": "Computer Science",
        "cgpa": 9.48,
        "semester": 8,
        "attendance": 91.0,
        "email": "rohan.verma@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Vector DB Indexing",
    },
    {
        "id": "STU-1004",
        "rollNumber": "21DS001",
        "name": "Priya Nair",
        "department": "Data Science",
        "cgpa": 9.75,
        "semester": 6,
        "attendance": 98.0,
        "email": "priya.nair@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Automated Anomaly Detection",
    },
    {
        "id": "STU-1005",
        "rollNumber": "21AI001",
        "name": "Devansh Gupta",
        "department": "AI & ML",
        "cgpa": 9.58,
        "semester": 6,
        "attendance": 92.0,
        "email": "devansh.g@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Vision Transformer Benchmarks",
    },
    {
        "id": "STU-1006",
        "rollNumber": "21CS004",
        "name": "Rahul Sharma",
        "department": "Computer Science",
        "cgpa": 8.85,
        "semester": 6,
        "attendance": 88.0,
        "email": "rahul.s@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Realtime WebRTC Audio Bridge",
    },
    {
        "id": "STU-1007",
        "rollNumber": "21EC001",
        "name": "Diya Patel",
        "department": "Electronics",
        "cgpa": 9.32,
        "semester": 6,
        "attendance": 95.0,
        "email": "diya.patel@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "FPGA Hardware Acceleration",
    },
    {
        "id": "STU-1008",
        "rollNumber": "21EC002",
        "name": "Siddharth Rao",
        "department": "Electronics",
        "cgpa": 8.91,
        "semester": 6,
        "attendance": 89.0,
        "email": "siddharth.r@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Embedded IoT Sensor Node",
    },
    {
        "id": "STU-1009",
        "rollNumber": "21ME001",
        "name": "Kavya Singh",
        "department": "Mechanical",
        "cgpa": 9.15,
        "semester": 8,
        "attendance": 93.0,
        "email": "kavya.singh@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Finite Element Thermals",
    },
    {
        "id": "STU-1010",
        "rollNumber": "21ME002",
        "name": "Aditya Kulkarni",
        "department": "Mechanical",
        "cgpa": 8.42,
        "semester": 8,
        "attendance": 82.0,
        "email": "aditya.k@campus.edu",
        "status": "Active",
        "backlogs": 1,
        "projectTitle": "Solar Kinetic Generators",
    },
    {
        "id": "STU-1011",
        "rollNumber": "21CE001",
        "name": "Neha Joshi",
        "department": "Civil",
        "cgpa": 8.95,
        "semester": 8,
        "attendance": 90.0,
        "email": "neha.j@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Seismic Structural Analysis",
    },
    {
        "id": "STU-1012",
        "rollNumber": "21CE002",
        "name": "Vikram Mehta",
        "department": "Civil",
        "cgpa": 7.82,
        "semester": 6,
        "attendance": 74.0,
        "email": "vikram.m@campus.edu",
        "status": "Active",
        "backlogs": 1,
        "projectTitle": "Eco-Concrete Additives",
    },
]


def _build_initial_students() -> List[StudentRecord]:
    records: List[StudentRecord] = []
    # Load base seed students
    for raw in INITIAL_STUDENT_DATA:
        records.append(StudentRecord.model_validate(raw))

    # Generate additional records up to 100+ matching frontend mock dataset generator
    depts: List[StudentDepartment] = [
        "Computer Science",
        "Electronics",
        "Mechanical",
        "Civil",
        "Data Science",
        "AI & ML",
    ]
    first_names = [
        "Amit",
        "Bhavna",
        "Chetan",
        "Divya",
        "Eshaan",
        "Farhan",
        "Gauri",
        "Harsh",
        "Indu",
        "Jay",
        "Kriti",
        "Lalit",
        "Maya",
        "Naveen",
        "Ojas",
        "Pooja",
        "Qasim",
        "Rashmi",
        "Sameer",
        "Trisha",
    ]
    last_names = [
        "Chaudhary",
        "Iyer",
        "Desai",
        "Banerjee",
        "Rao",
        "Nambiar",
        "Ghosh",
        "Chatterjee",
        "Mishra",
        "Trivedi",
    ]

    dept_codes = {
        "Computer Science": "CS",
        "Electronics": "EC",
        "Mechanical": "ME",
        "Civil": "CE",
        "Data Science": "DS",
        "AI & ML": "AI",
    }

    id_counter = 1013
    for i in range(90):
        dept = depts[i % len(depts)]
        fn = first_names[i % len(first_names)]
        ln = last_names[(i * 3) % len(last_names)]
        sem = (i % 8) + 1
        cgpa = round(6.2 + ((i * 3.7) % 3.7), 2)
        attendance = float(62 + ((i * 37) % 37))
        backlogs = (i % 3) + 1 if cgpa < 7.0 else 0
        status = "Probation" if cgpa < 6.8 else ("Graduated" if sem == 8 else "Active")

        records.append(
            StudentRecord(
                id=f"STU-{id_counter}",
                roll_number=f"21{dept_codes[dept]}{(i % 50) + 10:03d}",
                name=f"{fn} {ln}",
                department=dept,
                cgpa=cgpa,
                semester=sem,
                attendance=attendance,
                email=f"{fn.lower()}.{ln.lower()}@campus.edu",
                status=status,
                backlogs=backlogs,
                project_title=f"{dept} Research Module {i + 1}",
            )
        )
        id_counter += 1

    return records


class StudentService:
    """Supabase-backed Student Service storing student records."""

    def get_students(self) -> List[StudentRecord]:
        raw_students = get_all_students()
        return [StudentRecord.model_validate(s) for s in raw_students]

    def reset_db(self) -> List[StudentRecord]:
        delete_all_students()
        initial_students = _build_initial_students()
        records_to_insert = [s.model_dump(by_alias=True) for s in initial_students]
        bulk_insert_students(records_to_insert)
        return self.get_students()


student_service = StudentService()
