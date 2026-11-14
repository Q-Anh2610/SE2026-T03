"""Executable API harness; fixture auth, không đăng ký vào production main.py."""
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import install_error_handlers
from app.ingestion.export_metadata import ExportPrincipal, ExportRequest, authorize, export_metadata


def create_export_app(engine, grants):
    app = FastAPI(title='VT-011 export harness')
    install_error_handlers(app)
    # Snapshot immutable grants: client headers/body không thể tự cấp quyền.
    principals = {token: ExportPrincipal(value['can_export'], frozenset(value['sources']))
                  for token, value in grants.items()}
    bearer = HTTPBearer(auto_error=False)

    def authorized_request(
        params: ExportRequest,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ):
        principal = principals.get(credentials.credentials) if credentials else None
        authorize(principal, params.source)
        return principal, params

    @app.get('/healthz')
    def health():
        return {'status': 'ok'}

    @app.post('/api/v1/exports/assets', responses={
        400: {'description':'Invalid request'}, 401: {'description':'Unauthenticated'},
        403: {'description':'Forbidden'}, 413: {'description':'Too many records'},
        503: {'description':'Export unavailable'},
    })
    def download_export(authorized: Annotated[tuple, Depends(authorized_request)]):
        principal, params = authorized
        with Session(engine) as session:
            document = export_metadata(session, principal, params)
        return JSONResponse(document, headers={
            'Content-Disposition': 'attachment; filename="assets.json"',
            'Cache-Control': 'no-store',
        })

    return app
