"""Modelos de dados persistidos no SQLite.

Todos os registros representam **despesas**; o campo ``expense_type`` guarda o
texto livre recebido na coluna ``TIPO`` do CSV e é usado para classificar/filtrar.
"""

from datetime import date, datetime
from decimal import Decimal

from .extensions import db

SOURCE_LABELS = {"cartao": "Cartão", "banco": "Banco"}

#: Tipos de despesa usados quando o arquivo não traz a coluna TIPO preenchida.
SEM_TIPO = "SEM TIPO"


class ImportBatch(db.Model):
    """Registro de cada arquivo CSV importado."""

    __tablename__ = "import_batch"

    id: int = db.Column(db.Integer, primary_key=True)
    filename: str = db.Column(db.String(255), nullable=False)
    imported_at: datetime = db.Column(db.DateTime, nullable=False, default=datetime.now)
    total_rows: int = db.Column(db.Integer, nullable=False, default=0)
    imported_rows: int = db.Column(db.Integer, nullable=False, default=0)
    duplicated_rows: int = db.Column(db.Integer, nullable=False, default=0)
    invalid_rows: int = db.Column(db.Integer, nullable=False, default=0)
    error_message: str | None = db.Column(db.Text)
    warnings: str | None = db.Column(db.Text)

    movements = db.relationship(
        "Movement",
        back_populates="batch",
        cascade="all, delete-orphan",
    )

    @property
    def status(self) -> str:
        if self.error_message:
            return "erro"
        if self.imported_rows == 0 and self.duplicated_rows > 0:
            return "duplicado"
        return "ok"

    @property
    def status_class(self) -> str:
        return {
            "ok": "success",
            "duplicado": "warning",
            "erro": "danger",
        }.get(self.status, "secondary")


class Movement(db.Model):
    """Uma despesa (cartão de crédito ou conta bancária)."""

    __tablename__ = "movement"

    id: int = db.Column(db.Integer, primary_key=True)
    movement_date: date = db.Column(db.Date, nullable=False, index=True)
    description: str = db.Column(db.String(255), nullable=False, default="")
    amount: Decimal = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    expense_type: str = db.Column(
        db.String(120), nullable=False, default=SEM_TIPO, index=True
    )
    local: str = db.Column(db.String(255), nullable=False, default="")
    bank: str = db.Column(db.String(120), nullable=False, default="", index=True)
    card: str = db.Column(db.String(120), nullable=False, default="", index=True)
    source: str = db.Column(db.String(20), nullable=False, index=True)
    fingerprint: str = db.Column(db.String(64), nullable=False, unique=True, index=True)
    batch_id: int = db.Column(
        db.Integer, db.ForeignKey("import_batch.id", ondelete="CASCADE"), index=True
    )
    created_at: datetime = db.Column(db.DateTime, nullable=False, default=datetime.now)

    batch = db.relationship("ImportBatch", back_populates="movements")

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS.get(self.source, self.source)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Movement {self.movement_date} {self.description} {self.amount}>"
