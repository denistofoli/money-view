"""Application Factory da aplicação Money View."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Flask
from dotenv import load_dotenv

from .extensions import db

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def _format_brl(value: Decimal | float | int | None) -> str:
    """Formata um número no padrão monetário brasileiro (1.234,56)."""
    if value is None:
        return "0,00"
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return "0,00"
    formatted = f"{abs(amount):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-{formatted}" if amount < 0 else formatted


def _format_date_br(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _ensure_schema() -> None:
    """Cria as tabelas e recria o esquema antigo (baseada em ``direction``)."""
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "movement" in tables:
        columns = {column["name"] for column in inspector.get_columns("movement")}
        if "expense_type" not in columns or "direction" in columns:
            db.drop_all()
            print(
                "money-view: esquema antigo detectado (campo 'direction'); "
                "tabelas recriadas — reimporte os arquivos CSV."
            )
    db.create_all()


def create_app(test_config: dict | None = None) -> Flask:
    load_dotenv(BASE_DIR / ".env")
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__, instance_path=str(INSTANCE_DIR), instance_relative_config=False)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "money-view-dev-local"),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'money_view.db'}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,
        PAGE_SIZE=50,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from .routes.imports import imports_bp
    from .routes.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(imports_bp)

    app.jinja_env.filters["brl"] = _format_brl
    app.jinja_env.filters["date_br"] = _format_date_br

    with app.app_context():
        from . import models  # noqa: F401  (registra os modelos no metadata)

        _ensure_schema()

    return app
