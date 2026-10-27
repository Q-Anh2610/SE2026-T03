"""API danh sách và chi tiết asset dùng chung session/service PostgreSQL."""

from typing import Annotated
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from app.api.examples import ASSET_EXAMPLE, PAGINATION_EXAMPLE, response_example
from app.api.mock import ERROR_RESPONSES
from app.db.dependencies import get_db_session
from app.schemas.api import AssetDetailResponse, AssetListQuery, AssetListResponse
from app.services.assets import get_asset, list_assets

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


def detail_identifier(asset_id: Annotated[str, Path(min_length=1, max_length=128)]) -> str:
    return asset_id


def detail_session(request: Request, asset_id: Annotated[str, Depends(detail_identifier)]) -> Iterator[Session]:
    yield from get_db_session(request)


@router.get("/assets/{asset_id}", response_model=AssetDetailResponse, tags=["assets"],
            summary="Chi tiết asset từ PostgreSQL",
            description="Tra cứu asset_id chính xác. Metadata và preview dùng cùng quy ước với list; không fallback fixture.",
            responses={200: response_example({
                "asset": {**ASSET_EXAMPLE, "asset_id": "mock-asset-001", "source": "mock"},
                "mock": False,
            })})
def get_asset_detail(asset_id: Annotated[str, Depends(detail_identifier)],
                     session: Annotated[Session, Depends(detail_session)]):
    return get_asset(session, asset_id)
