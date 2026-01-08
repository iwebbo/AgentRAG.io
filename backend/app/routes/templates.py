from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import re

from app.database import get_db
from app.models import User, Template
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateRenderRequest,
    TemplateRenderResponse
)
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/templates", tags=["Templates"])


@router.get("/", response_model=List[TemplateResponse])
async def list_templates(
    include_public: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List templates for current user and optionally public templates"""
    
    query = db.query(Template)
    
    if include_public:
        # User's templates OR public templates
        query = query.filter(
            (Template.user_id == current_user.id) | (Template.is_public == True)
        )
    else:
        # Only user's templates
        query = query.filter(Template.user_id == current_user.id)
    
    templates = query.order_by(Template.created_at.desc()).all()
    
    return templates


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new template"""
    
    template = Template(
        user_id=current_user.id,
        **template_data.model_dump()
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return template


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get template by ID"""
    
    template = db.query(Template).filter(
        Template.id == template_id
    ).filter(
        (Template.user_id == current_user.id) | (Template.is_public == True)
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    template_update: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update template"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.user_id == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Update fields
    update_data = template_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    db.commit()
    db.refresh(template)
    
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete template"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.user_id == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    db.delete(template)
    db.commit()
    
    return None


@router.post("/{template_id}/render", response_model=TemplateRenderResponse)
async def render_template(
    template_id: UUID,
    render_data: TemplateRenderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Render template with variables"""
    
    template = db.query(Template).filter(
        Template.id == template_id
    ).filter(
        (Template.user_id == current_user.id) | (Template.is_public == True)
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Render template
    rendered_content = template.content
    
    for variable, value in render_data.variables.items():
        # Replace {{variable}} with value
        pattern = r'\{\{' + re.escape(variable) + r'\}\}'
        rendered_content = re.sub(pattern, str(value), rendered_content)
    
    # Check for unreplaced variables
    unreplaced = re.findall(r'\{\{(\w+)\}\}', rendered_content)
    if unreplaced:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing variables: {', '.join(unreplaced)}"
        )
    
    return TemplateRenderResponse(rendered_content=rendered_content)