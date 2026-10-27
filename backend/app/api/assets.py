"""API asset dùng PostgreSQL. Detail sẽ được triển khai ở issue riêng."""

from typing import Annotated
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.examples import ASSET_EXAMPLE, PAGINATION_EXAMPLE, response_example
from app.api.mock import ERROR_RESPONSES
from app.db.dependencies import get_db_session
from app.schemas.api import AssetListQuery, AssetListResponse
from app.services.assets import list_assets

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


def list_parameters(params: Annotated[AssetListQuery, Query()]) -> AssetListQuery:
    return params


def list_session(request: Request, params: Annotated[AssetListQuery, Depends(list_parameters)]) -> Iterator[Session]:
    # Validation phải xong trước khi đọc cấu hình/kết nối DB, kể cả khi DB lỗi.
    yield from get_db_session(request)


@router.get("/assets", response_model=AssetListResponse, tags=["assets"],
            summary="Danh sách asset từ PostgreSQL",
            description="Filters AND trước phân trang; sắp xếp asset_id tăng dần. Không fallback mock khi DB lỗi.",
            responses={200: response_example({
                "items": [{**ASSET_EXAMPLE, "asset_id": "mock-asset-001", "source": "mock"}],
                "pagination": PAGINATION_EXAMPLE, "mock": False,
            })})
def get_assets(params: Annotated[AssetListQuery, Depends(list_parameters)],
               session: Annotated[Session, Depends(list_session)]):
    return list_assets(session, params)
