"""Rotas de importação de arquivos CSV e histórico de importações."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select

from ..extensions import db
from ..models import ImportBatch, Movement
from ..services.csv_importer import CsvImportError, parse_csv

imports_bp = Blueprint("imports", __name__)

CHUNK_SIZE = 500


def _existing_fingerprints(fingerprints: set[str]) -> set[str]:
    found: set[str] = set()
    values = list(fingerprints)
    for start in range(0, len(values), CHUNK_SIZE):
        chunk = values[start : start + CHUNK_SIZE]
        found.update(
            db.session.scalars(
                select(Movement.fingerprint).where(Movement.fingerprint.in_(chunk))
            ).all()
        )
    return found


@imports_bp.route("/importar", methods=["GET", "POST"])
def import_files():
    if request.method == "POST":
        files = [item for item in request.files.getlist("arquivos") if item and item.filename]
        if not files:
            flash("Selecione ao menos um arquivo CSV para importar.", "warning")
            return redirect(url_for("imports.import_files"))

        processed = 0
        imported_total = 0
        duplicate_total = 0
        invalid_total = 0
        errors: list[str] = []

        for storage in files:
            filename = (storage.filename or "arquivo.csv").rsplit("/", 1)[-1][:255]
            batch = ImportBatch(filename=filename)
            db.session.add(batch)
            db.session.flush()

            try:
                result = parse_csv(storage.read())
            except CsvImportError as exc:
                batch.error_message = str(exc)
                batch.total_rows = 0
                errors.append(f"{filename}: {exc}")
                db.session.commit()
                continue

            batch.total_rows = len(result.rows) + result.invalid_rows
            batch.invalid_rows = result.invalid_rows
            batch.warnings = " | ".join(result.warnings) or None
            invalid_total += result.invalid_rows

            existing = _existing_fingerprints({row.fingerprint for row in result.rows})
            imported = 0
            duplicated = 0
            for row in result.rows:
                if row.fingerprint in existing:
                    duplicated += 1
                    continue
                existing.add(row.fingerprint)
                db.session.add(
                    Movement(
                        movement_date=row.movement_date,
                        description=row.description,
                        amount=row.amount,
                        expense_type=row.expense_type,
                        local=row.local,
                        bank=row.bank,
                        card=row.card,
                        source=row.source,
                        fingerprint=row.fingerprint,
                        batch=batch,
                    )
                )
                imported += 1

            batch.imported_rows = imported
            batch.duplicated_rows = duplicated
            db.session.commit()

            processed += 1
            imported_total += imported
            duplicate_total += duplicated
            if result.errors:
                errors.extend(f"{filename} — {message}" for message in result.errors)
            if result.warnings:
                errors.extend(f"{filename} — {message}" for message in result.warnings)

        if processed:
            flash(
                f"{processed} arquivo(s) processado(s): {imported_total} movimentação(ões) "
                f"importada(s), {duplicate_total} duplicada(s) ignorada(s), "
                f"{invalid_total} linha(s) inválida(s).",
                "success" if imported_total else "info",
            )
        if errors:
            flash(" | ".join(errors[:5]), "warning")

        return redirect(url_for("imports.import_files"))

    batches = db.session.scalars(
        select(ImportBatch).order_by(ImportBatch.imported_at.desc(), ImportBatch.id.desc())
    ).all()
    movements_total = db.session.scalar(select(func.count(Movement.id))) or 0

    return render_template(
        "import.html",
        batches=batches,
        movements_total=movements_total,
    )


@imports_bp.post("/importacoes/<int:batch_id>/excluir")
def delete_batch(batch_id: int):
    batch = db.session.get(ImportBatch, batch_id)
    if batch is None:
        flash("Importação não encontrada.", "warning")
        return redirect(url_for("imports.import_files"))

    db.session.delete(batch)
    db.session.commit()
    flash(f"Importação de '{batch.filename}' removida com sucesso.", "success")
    return redirect(url_for("imports.import_files"))
