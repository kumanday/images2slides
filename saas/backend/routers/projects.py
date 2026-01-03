from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import Project, ProjectStatus, User
from ..db.session import get_db
from ..schemas import ProjectCreateIn, ProjectOut, ProjectUpdateIn
from ..services.auth import get_current_user

router = APIRouter()


def _get_project(db: Session, user_id: int, project_id: int) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.user_id == user_id, Project.status != ProjectStatus.archived)
        .options(selectinload(Project.images))
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/projects", response_model=ProjectOut)
def create_project(
    body: ProjectCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = Project(user_id=user.id, title=body.title, page_size=body.page_size)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Project]:
    projects = db.scalars(
        select(Project)
        .where(Project.user_id == user.id, Project.status != ProjectStatus.archived)
        .order_by(Project.updated_at.desc())
        .options(selectinload(Project.images))
    ).all()
    return list(projects)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    return _get_project(db, user.id, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = _get_project(db, user.id, project_id)

    if body.title is not None:
        project.title = body.title
    if body.page_size is not None:
        project.page_size = body.page_size

    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    project = _get_project(db, user.id, project_id)
    project.status = ProjectStatus.archived
    db.commit()
    return {"status": "archived"}
