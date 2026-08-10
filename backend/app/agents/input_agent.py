from typing import Optional, Dict, Any
from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult

DEPARTMENTS = [
    "Computer Science",
    "Electronics",
    "Mechanical",
    "Civil",
    "Data Science",
    "AI & ML",
]


class InputAgent(BaseAgent):
    name = "input"

    def execute(self, task: AgentTask) -> AgentResult:
        query = task.input_data.get("user_query", "")
        query_lower = query.lower()

        # Extract department filter
        dept_match: Optional[str] = None
        for d in DEPARTMENTS:
            if d.lower() in query_lower:
                dept_match = d
                break

        # Check department shortcodes
        if not dept_match:
            if " cs " in f" {query_lower} " or " cs" in query_lower:
                dept_match = "Computer Science"
            elif " ec " in f" {query_lower} " or " electronics" in query_lower:
                dept_match = "Electronics"
            elif " me " in f" {query_lower} " or " mechanical" in query_lower:
                dept_match = "Mechanical"
            elif " ce " in f" {query_lower} " or " civil" in query_lower:
                dept_match = "Civil"
            elif " ds " in f" {query_lower} " or " data science" in query_lower:
                dept_match = "Data Science"
            elif " ai " in f" {query_lower} " or " ml " in f" {query_lower} ":
                dept_match = "AI & ML"

        # Extract CGPA constraint
        min_cgpa: Optional[float] = None
        if "top" in query_lower or "high" in query_lower:
            min_cgpa = 9.0
        elif "cgpa >" in query_lower or "cgpa >=" in query_lower:
            min_cgpa = 8.0

        # Extract limit
        limit = 100
        words = query_lower.split()
        for i, word in enumerate(words):
            if word in ["top", "limit", "first"] and i + 1 < len(words):
                if words[i + 1].isdigit():
                    limit = int(words[i + 1])

        intent_type = (
            "student_update"
            if any(w in query_lower for w in ["update", "modify", "change", "delete"])
            else "student_query"
        )

        structured_intent = {
            "intent": intent_type,
            "department": dept_match,
            "min_cgpa": min_cgpa,
            "limit": limit,
            "original_query": query,
        }

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={"structured_intent": structured_intent},
        )