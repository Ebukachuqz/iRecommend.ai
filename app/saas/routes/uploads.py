from __future__ import annotations

import json
import threading
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status

from app.saas.auth import get_current_user_id, validate_organisation_owner
from app.saas.db import get_saas_client
from app.saas.models import UploadCreateResponse, UploadStatusResponse
from app.saas.services.csv_processor import (
    MerchantCsvProcessor,
    count_csv_rows,
    normalize_mapping,
    validate_product_mapping,
    validate_review_mapping,
)


router = APIRouter(prefix="/saas", tags=["saas-uploads"])


def parse_column_mapping(raw_mapping: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column_mapping must be valid JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column_mapping must be a JSON object.",
        )
    return payload


def initial_processing_summary() -> dict[str, Any]:
    return {
        "customers_detected": 0,
        "valid_rows": 0,
        "skipped_invalid_rows": 0,
        "skipped_insufficient_reviews": 0,
        "failed_personas": 0,
        "error_samples": [],
    }


def create_upload_record(
    *,
    org_id: str,
    upload_type: str,
    file_name: str,
    mapping: dict[str, Any],
    total_rows: int,
) -> str:
    try:
        response = (
            get_saas_client()
            .table("csv_uploads")
            .insert(
                {
                    "organisation_id": org_id,
                    "upload_type": upload_type,
                    "file_name": file_name,
                    "column_mapping": mapping,
                    "status": "pending",
                    "total_rows": total_rows,
                    "processed_rows": 0,
                    "personas_generated": 0,
                    "processing_summary": initial_processing_summary(),
                }
            )
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create upload record. Ensure csv_uploads.processing_summary exists.",
        ) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload record was not created.",
        )
    return str(rows[0]["id"])


@router.post("/uploads/reviews", response_model=UploadCreateResponse)
async def upload_reviews_csv(
    authorization: Annotated[str | None, Header()] = None,
    file: UploadFile = File(...),
    column_mapping: str = Form(...),
    org_id: str = Form(...),
) -> UploadCreateResponse:
    user_id = get_current_user_id(authorization)
    validate_organisation_owner(org_id, user_id)
    mapping = parse_column_mapping(column_mapping)
    try:
        validate_review_mapping(normalize_mapping(mapping))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a CSV file.")

    file_content = await file.read()
    total_rows = count_csv_rows(file_content)
    upload_id = create_upload_record(
        org_id=org_id,
        upload_type="reviews",
        file_name=file.filename,
        mapping=mapping,
        total_rows=total_rows,
    )

    thread = threading.Thread(
        target=MerchantCsvProcessor().process_reviews_csv,
        kwargs={
            "file_content": file_content,
            "column_mapping": mapping,
            "org_id": org_id,
            "upload_id": upload_id,
        },
        daemon=True,
    )
    thread.start()
    return UploadCreateResponse(upload_id=upload_id, total_rows=total_rows)


@router.post("/uploads/products", response_model=UploadCreateResponse)
async def upload_products_csv(
    authorization: Annotated[str | None, Header()] = None,
    file: UploadFile = File(...),
    column_mapping: str = Form(...),
    org_id: str = Form(...),
) -> UploadCreateResponse:
    user_id = get_current_user_id(authorization)
    validate_organisation_owner(org_id, user_id)
    mapping = parse_column_mapping(column_mapping)
    try:
        validate_product_mapping(normalize_mapping(mapping))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a CSV file.")

    file_content = await file.read()
    total_rows = count_csv_rows(file_content)
    upload_id = create_upload_record(
        org_id=org_id,
        upload_type="products",
        file_name=file.filename,
        mapping=mapping,
        total_rows=total_rows,
    )

    thread = threading.Thread(
        target=MerchantCsvProcessor().process_products_csv,
        kwargs={
            "file_content": file_content,
            "column_mapping": mapping,
            "org_id": org_id,
            "upload_id": upload_id,
        },
        daemon=True,
    )
    thread.start()
    return UploadCreateResponse(upload_id=upload_id, total_rows=total_rows)


@router.get("/uploads/{upload_id}/status", response_model=UploadStatusResponse)
def get_upload_status(
    upload_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> UploadStatusResponse:
    user_id = get_current_user_id(authorization)
    response = (
        get_saas_client()
        .table("csv_uploads")
        .select("*")
        .eq("id", upload_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")

    upload = dict(rows[0])
    validate_organisation_owner(str(upload["organisation_id"]), user_id)
    return UploadStatusResponse(
        upload_id=str(upload["id"]),
        upload_type=str(upload.get("upload_type") or ""),
        status=str(upload.get("status") or "pending"),
        total_rows=int(upload.get("total_rows") or 0),
        processed_rows=int(upload.get("processed_rows") or 0),
        personas_generated=int(upload.get("personas_generated") or 0),
        error_message=upload.get("error_message"),
        processing_summary=dict(upload.get("processing_summary") or {}),
    )
