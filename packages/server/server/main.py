from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import get_settings
from server.routes.runs import router as runs_router
from server.routes.bars import router as bars_router
from server.routes.fills import router as fills_router
from server.routes.positions import router as positions_router
from server.routes.account import router as account_router
from server.routes.indicators import router as indicators_router
from server.routes.catalog import router as catalog_router
from server.routes.catalog_bars import router as catalog_bars_router
from server.routes.version import VERSION, router as version_router
from server.routes.strategies import router as strategies_router


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Nautilus Automatron", version=VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://localhost:\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(runs_router, prefix="/api")
    app.include_router(indicators_router, prefix="/api")  # Before bars — indicators path must match before {bar_type:path}
    app.include_router(bars_router, prefix="/api")
    app.include_router(fills_router, prefix="/api")
    app.include_router(positions_router, prefix="/api")
    app.include_router(account_router, prefix="/api")
    app.include_router(catalog_router, prefix="/api")
    app.include_router(catalog_bars_router, prefix="/api")
    app.include_router(version_router, prefix="/api")
    app.include_router(strategies_router, prefix="/api")

    return app


app = create_app()
