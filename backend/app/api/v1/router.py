from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    dashboard,
    documents,
    encrypted_journals,
    focus,
    health,
    journals,
    note_folders,
    notes,
    problems,
    schedules,
    statistics,
    tasks,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(tasks.router)
api_router.include_router(focus.router)
api_router.include_router(encrypted_journals.router)
api_router.include_router(journals.router)
api_router.include_router(notes.router)

api_router.include_router(note_folders.router)
api_router.include_router(documents.router)
api_router.include_router(schedules.router)
api_router.include_router(dashboard.router)
api_router.include_router(problems.router)
api_router.include_router(statistics.router)
