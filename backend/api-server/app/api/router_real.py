from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, dedup, knowledge_real, projects_real

api_router_real = APIRouter()
api_router_real.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router_real.include_router(projects_real.router, prefix="/projects", tags=["projects"])
api_router_real.include_router(knowledge_real.router, prefix="/projects/{project_id}/knowledge", tags=["knowledge"])
api_router_real.include_router(dedup.router, prefix="/projects/{project_id}/knowledge/dedup", tags=["dedup"])
api_router_real.include_router(chat.router, prefix="/projects/{project_id}/chat", tags=["chat"])
