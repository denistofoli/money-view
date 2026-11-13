"""Rotas de visualização e filtro das despesas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, current_app, render_template, request
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import SEM_TIPO, Movement

main_bp = Blueprint("main", __name__)

SORT_OPTIONS = {
    "data_desc": "Data (mais recente)",
    "data_asc": "Data (mais antiga)",
    "valor_desc": "Valor (maior)",
    "valor_asc": "Valor (menor)",
}
SOURCE_OPTIONS = {
    "": "Todas as origens",
    "cartao": "Cartão de crédito",
    "banco": "Conta bancária",
}


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _clean(value: str | None) -> str:
    return (value or "").strip()


@main_bp.route("/")
def index():
    args = request.args

    start_date = _parse_iso_date(args.get("data_inicio"))
    end_date = _parse_iso_date(args.get("data_fim"))
    expense_type = _clean(args.get("tipo"))
    source = args.get("fonte", "") if args.get("fonte") in SOURCE_OPTIONS else ""
    bank = _clean(args.get("banco"))
    card = _clean(args.get("cartao"))
    term = _clean(args.get("q"))
    sort = args.get("ordenar", "data_desc")
    if sort not in SORT_OPTIONS:
        sort = "data_desc"

    conditions = []
    if start_date:
        conditions.append(Movement.movement_date >= start_date)
    if end_date:
        conditions.append(Movement.movement_date <= end_date)
    if expense_type:
        conditions.append(Movement.expense_type == expense_type)
    if source:
        conditions.append(Movement.source == source)
    if bank:
        conditions.append(Movement.bank == bank)
    if card:
        conditions.append(Movement.card == card)
    if term:
        like = f"%{term}%"
        conditions.append(
            or_(
                Movement.description.ilike(like),
                Movement.local.ilike(like),
                Movement.expense_type.ilike(like),
                Movement.bank.ilike(like),
                Movement.card.ilike(like),
            )
        )

    totals_stmt = select(
        func.coalesce(func.sum(Movement.amount), 0),
        func.count(Movement.id),
        func.coalesce(func.max(Movement.amount), 0),
    ).where(*conditions)
    total_raw, count, biggest_raw = db.session.execute(totals_stmt).one()

    total = Decimal(str(total_raw or 0))
    biggest = Decimal(str(biggest_raw or 0))
    average = (total / count) if count else Decimal("0")

    order_by = {
        "data_desc": (Movement.movement_date.desc(), Movement.id.desc()),
        "data_asc": (Movement.movement_date.asc(), Movement.id.asc()),
        "valor_desc": (Movement.amount.desc(), Movement.movement_date.desc()),
        "valor_asc": (Movement.amount.asc(), Movement.movement_date.desc()),
    }[sort]

    stmt = select(Movement).where(*conditions).order_by(*order_by)
    page = args.get("page", type=int) or 1
    pagination = db.paginate(
        stmt,
        page=page,
        per_page=current_app.config["PAGE_SIZE"],
        error_out=False,
    )

    breakdown_rows = db.session.execute(
        select(
            Movement.expense_type,
            func.count(Movement.id),
            func.coalesce(func.sum(Movement.amount), 0),
        )
        .where(*conditions)
        .group_by(Movement.expense_type)
        .order_by(func.sum(Movement.amount).desc(), Movement.expense_type.asc())
    ).all()
    breakdown = [
        {
            "expense_type": row[0] or SEM_TIPO,
            "count": row[1],
            "total": Decimal(str(row[2] or 0)),
            "share": (Decimal(str(row[2] or 0)) / total * 100) if total else Decimal("0"),
        }
        for row in breakdown_rows
    ]

    expense_types = db.session.scalars(
        select(Movement.expense_type)
        .where(Movement.expense_type != "")
        .distinct()
        .order_by(Movement.expense_type.asc())
    ).all()
    banks = db.session.scalars(
        select(Movement.bank)
        .where(Movement.bank != "")
        .distinct()
        .order_by(Movement.bank.asc())
    ).all()
    cards = db.session.scalars(
        select(Movement.card)
        .where(Movement.card != "")
        .distinct()
        .order_by(Movement.card.asc())
    ).all()

    filters = {
        "data_inicio": args.get("data_inicio", ""),
        "data_fim": args.get("data_fim", ""),
        "tipo": expense_type,
        "fonte": source,
        "banco": bank,
        "cartao": card,
        "q": term,
        "ordenar": sort,
    }
    filter_args = {key: value for key, value in filters.items() if value}
    has_filters = bool(filter_args)

    return render_template(
        "index.html",
        movements=pagination.items,
        pagination=pagination,
        total=total,
        count=count,
        average=average,
        biggest=biggest,
        breakdown=breakdown,
        filters=filters,
        filter_args=filter_args,
        has_filters=has_filters,
        expense_types=expense_types,
        banks=banks,
        cards=cards,
        source_options=SOURCE_OPTIONS,
        sort_options=SORT_OPTIONS,
        start_date=start_date,
        end_date=end_date,
    )
