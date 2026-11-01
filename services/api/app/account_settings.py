"""Explicit self-profile and owner-managed basic workspace settings."""

from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import EmailStr, Field
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuditEvent, User
from .schemas import StrictModel
from .security import Tenant, current_user, lock_org, require, tenant_context

router = APIRouter()


class AccountInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(default="", max_length=40, pattern=r"^[0-9+() .-]*$")


def profile(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "has_photo": bool(user.avatar_data),
        "google_linked": bool(user.google_subject),
    }


@router.get("/api/auth/profile")
def get_profile(user: User = Depends(current_user)):
    return profile(user)


@router.put("/api/auth/profile")
def save_profile(
    body: AccountInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    user.name = body.name
    user.phone = body.phone
    db.commit()
    return profile(user)


@router.get("/api/auth/profile/photo")
def get_photo(user: User = Depends(current_user)):
    if not user.avatar_data:
        raise HTTPException(404, "No profile photo")
    return Response(
        user.avatar_data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/api/auth/profile/photo")
async def save_photo(
    request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 5 * 1024 * 1024:
            raise HTTPException(413, "Profile photo must be under 5 MB")
    try:
        with Image.open(BytesIO(body)) as image:
            if (
                image.format not in {"JPEG", "PNG", "WEBP"}
                or getattr(image, "n_frames", 1) != 1
            ):
                raise ValueError("Unsupported image")
            if image.width * image.height > 8_000_000:
                raise ValueError("Image dimensions too large")
            image.load()
            normalized = ImageOps.exif_transpose(image).convert("RGBA")
            normalized.thumbnail((256, 256))
            output_image = Image.new("RGB", normalized.size, "white")
            output_image.paste(normalized, mask=normalized.getchannel("A"))
            output_image.info.clear()
            output = BytesIO()
            output_image.save(output, format="JPEG", quality=85)
    except (
        UnidentifiedImageError,
        ValueError,
        OSError,
        Image.DecompressionBombError,
    ) as exc:
        raise HTTPException(
            422, "Choose a valid non-animated JPG, PNG or WebP photo up to 8 megapixels"
        ) from exc
    user.avatar_data = output.getvalue()
    user.avatar_mime = "image/jpeg"
    db.commit()
    return profile(user)


@router.delete("/api/auth/profile/photo", status_code=204)
def remove_photo(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.avatar_data = None
    user.avatar_mime = ""
    db.commit()
    return Response(status_code=204)


class WorkspaceInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    contact_phone: str = Field(default="", max_length=40)
    contact_email: EmailStr | Literal[""] = ""
    address: str = Field(default="", max_length=500)


def workspace(org):
    values = (org.business_profile or {}).get("basic_setup", {})
    return {
        "name": org.name,
        "contact_phone": values.get("contact_phone", ""),
        "contact_email": values.get("contact_email", ""),
        "address": values.get("address", ""),
        "currency": "LKR",
        "report_timezone": "Asia/Colombo",
        "business_type": org.business_type,
    }


@router.get("/api/workspace/basic-settings")
def basic_settings(
    tenant: Tenant = Depends(tenant_context), db: Session = Depends(get_db)
):
    return workspace(lock_org(db, tenant))


@router.put("/api/workspace/basic-settings")
def save_basic_settings(
    body: WorkspaceInput,
    tenant: Tenant = Depends(tenant_context),
    db: Session = Depends(get_db),
):
    require(tenant, "owner", "admin")
    org = lock_org(db, tenant)
    org.name = body.name
    org.business_profile = {
        **(org.business_profile or {}),
        "basic_setup": body.model_dump(exclude={"name"}, mode="json"),
    }
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action="workspace.basic_settings.updated",
            entity_id=tenant.id,
        )
    )
    db.commit()
    return workspace(org)
