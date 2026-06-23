from fastapi import APIRouter, Depends

from app.api.deps.auth import require_project_member
from app.api.v1.endpoints import admin_project_members, admin_users, auth, chat, chat_logs, datasets, dedup, document_qa, files, governance, knowledge, knowledge_bases, knowledge_compilation, portal, project_settings, projects, scenes, search

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(portal.router, prefix="/portal", tags=["portal"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["admin-users"])
api_router.include_router(
    admin_project_members.router,
    prefix="/admin/projects/{project_id}/members",
    tags=["admin-project-members"],
)
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(
    project_settings.router,
    prefix="/projects/{project_id}/settings",
    tags=["project-settings"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    knowledge_bases.router,
    prefix="/projects/{project_id}/knowledge/bases",
    tags=["knowledge-bases"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    files.router,
    prefix="/projects/{project_id}/knowledge/bases/{kb_id}/files",
    tags=["files"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    knowledge_compilation.router,
    prefix="/projects/{project_id}/knowledge/bases/{kb_id}/compilation",
    tags=["knowledge-compilation"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    document_qa.router,
    prefix="/projects/{project_id}/document-qa",
    tags=["document-qa"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    knowledge.router,
    prefix="/projects/{project_id}/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    dedup.router,
    prefix="/projects/{project_id}/knowledge/dedup",
    tags=["dedup"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    governance.router,
    prefix="/projects/{project_id}/knowledge/governance",
    tags=["governance"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    chat.router,
    prefix="/projects/{project_id}/chat",
    tags=["chat"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    scenes.router,
    prefix="/projects/{project_id}/scenes",
    tags=["scenes"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    search.router,
    prefix="/projects/{project_id}/search",
    tags=["search"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    datasets.router,
    prefix="/projects/{project_id}/datasets",
    tags=["datasets"],
    dependencies=[Depends(require_project_member)],
)
api_router.include_router(
    chat_logs.router,
    prefix="/projects/{project_id}/logs/chat",
    tags=["chat-logs"],
    dependencies=[Depends(require_project_member)],
)
