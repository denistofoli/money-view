"""Leitura e normalização dos arquivos CSV de despesas.

Estrutura esperada do arquivo (separador ``;``)::

    DATA;DESCRICAO;VALOR;TIPO;LOCAL;BANCO;CARTAO

``TIPO`` é texto livre (ex.: ``ALIMENTACAO``, ``TRANSPORTE``) e é preservado para
servir de filtro. A resolução das colunas é tolerante: primeiro por nome (com
sinônimos), depois por conteúdo (data/valor) e, por fim, pela posição do layout
documentado — assim a ``DESCRICAO`` nunca é perdida por um cabeçalho diferente.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ("data", "descricao", "valor", "tipo", "local", "banco", "cartao")

#: Ordem posicional do layout documentado.
POSITIONAL_ORDER = REQUIRED_COLUMNS

#: Sinônimos aceitos para cada campo do layout.
COLUMN_ALIASES: dict[str, set[str]] = {
    "data": {
        "data",
        "dt",
        "date",
        "data_movimento",
        "data_movimentacao",
        "data_lancamento",
        "data_da_compra",
        "data_compra",
        "data_transacao",
    },
    "descricao": {
        "descricao",
        "desc",
        "descricao_lancamento",
        "descricao_do_lancamento",
        "descricao_movimento",
        "descricao_movimentacao",
        "descricao_transacao",
        "historico",
        "historico_lancamento",
        "lancamento",
        "detalhe",
        "detalhes",
        "detalhe_lancamento",
        "estabelecimento",
        "titulo",
    },
    "valor": {
        "valor",
        "vlr",
        "value",
        "valor_r",
        "valor_rs",
        "valor_reais",
        "valor_lancamento",
        "valor_despesa",
        "montante",
    },
    "tipo": {
        "tipo",
        "type",
        "tipo_despesa",
        "tipo_de_despesa",
        "tipo_lancamento",
        "tipo_movimento",
        "categoria",
        "classificacao",
        "grupo",
        "classe",
    },
    "local": {"local", "localizacao", "cidade", "place", "municipio"},
    "banco": {"banco", "bank", "instituicao", "emissor", "conta"},
    "cartao": {
        "cartao",
        "card",
        "cartao_credito",
        "cartao_de_credito",
        "final_cartao",
        "numero_cartao",
        "cartao_final",
        "final",
    },
}

DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


class CsvImportError(ValueError):
    """Erro de estrutura/leitura do arquivo CSV."""


@dataclass
class ParsedRow:
    movement_date: date
    description: str
    amount: Decimal
    expense_type: str
    local: str
    bank: str
    card: str
    source: str
    fingerprint: str


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    invalid_rows: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_header(value: str) -> str:
    cleaned = _strip_accents(value or "").strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
    return cleaned


def _normalize_text(value: str | None, max_length: int = 255) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    return text[:max_length]


def decode_content(content: bytes) -> str:
    """Decodifica o arquivo tentando UTF-8 e, como fallback, Windows-1252/Latin-1."""
    if not content or not content.strip():
        raise CsvImportError("O arquivo está vazio.")
    for encoding in ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1", errors="replace")


def detect_delimiter(sample: str) -> str:
    first_line = next((line for line in sample.splitlines() if line.strip()), "")
    if ";" in first_line:
        return ";"
    if "\t" in first_line:
        return "\t"
    return ","


def parse_amount(raw: str | None) -> Decimal | None:
    """Converte valores nos formatos ``1.234,56``, ``1234.56``, ``R$ 45,90 D`` etc."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]

    text = text.replace("R$", "").replace("r$", "").replace(" ", " ").strip()

    match = re.fullmatch(
        r"(?P<lead>[A-Za-z]{1,2})?\s*(?P<num>[-+]?[\d.,]+)\s*(?P<trail>[A-Za-z]{1,2})?", text
    )
    if not match:
        return None
    lead, num, trail = match.group("lead"), match.group("num"), match.group("trail")
    suffix = (trail or lead or "").strip().upper()

    if num.startswith("-"):
        negative = True
        num = num[1:]
    elif num.startswith("+"):
        num = num[1:]

    if not re.fullmatch(r"[\d.,]+", num):
        return None

    has_comma, has_dot = "," in num, "." in num
    if has_comma and has_dot:
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif has_comma:
        num = num.replace(".", "").replace(",", ".")
    elif num.count(".") > 1:
        num = num.replace(".", "")
    elif has_dot:
        decimals = len(num.split(".")[-1])
        if decimals == 3:
            num = num.replace(".", "")

    try:
        value = Decimal(num)
    except (InvalidOperation, ValueError):
        return None

    if not value.is_finite():
        return None

    if suffix in {"D", "DB", "DR"}:
        negative = True
    elif suffix in {"C", "CR"}:
        negative = False

    value = value.quantize(Decimal("0.01"))
    return -value if negative else value


def parse_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    text = text.split(" ")[0].split("T")[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def build_fingerprint(
    movement_date: date,
    description: str,
    amount: Decimal,
    expense_type: str,
    local: str,
    bank: str,
    card: str,
    source: str,
) -> str:
    payload = "|".join(
        [
            movement_date.isoformat(),
            _strip_accents(description).lower(),
            f"{amount:.2f}",
            _strip_accents(expense_type).lower(),
            _strip_accents(local).lower(),
            _strip_accents(bank).lower(),
            _strip_accents(card).lower(),
            source,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_columns(
    header: list[str], sample_rows: list[list[str]]
) -> tuple[dict[str, int], list[str]]:
    """Mapeia campo canônico → índice da coluna, com fallback por conteúdo e posição."""
    columns = [_normalize_header(cell) for cell in header]
    mapping: dict[str, int] = {}
    used: set[int] = set()
    warnings: list[str] = []

    for field_name, aliases in COLUMN_ALIASES.items():
        for index, column in enumerate(columns):
            if index in used or not column:
                continue
            if column in aliases:
                mapping[field_name] = index
                used.add(index)
                break

    def sample_values(index: int) -> list[str]:
        return [row[index] for row in sample_rows if index < len(row) and str(row[index]).strip()]

    # Data/valor: se o nome não foi reconhecido, procura a coluna pelo conteúdo.
    for field_name, parser in (("data", parse_date), ("valor", parse_amount)):
        if field_name in mapping:
            continue
        best_index, best_score = None, 0.0
        for index in range(len(columns)):
            if index in used:
                continue
            values = sample_values(index)
            if not values:
                continue
            score = sum(1 for value in values if parser(value) is not None) / len(values)
            if score > best_score:
                best_index, best_score = index, score
        if best_index is not None and best_score >= 0.6:
            mapping[field_name] = best_index
            used.add(best_index)
            warnings.append(
                f"Coluna de {field_name.upper()} reconhecida pelo conteúdo (posição {best_index + 1})."
            )

    # Demais campos: posição do layout documentado.
    for index, field_name in enumerate(POSITIONAL_ORDER):
        if field_name in mapping or index in used or index >= len(columns):
            continue
        mapping[field_name] = index
        used.add(index)
        if field_name in {"descricao", "tipo"}:
            warnings.append(
                f"Coluna {field_name.upper()} não identificada pelo nome; usando a posição {index + 1}."
            )

    return mapping, warnings


def parse_csv(content: bytes) -> ParseResult:
    """Lê o conteúdo binário de um CSV e devolve as linhas válidas já normalizadas."""
    text = decode_content(content)
    delimiter = detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    all_rows = [row for row in reader if row and any(str(value).strip() for value in row)]
    if not all_rows:
        raise CsvImportError("O arquivo não possui linhas de dados.")

    header = all_rows[0]
    header_looks_like_data = parse_date(header[0] if header else None) is not None

    if header_looks_like_data:
        # Arquivo sem cabeçalho: assume o layout posicional documentado.
        mapping = {name: index for index, name in enumerate(POSITIONAL_ORDER)}
        data_rows = all_rows
        warnings = ["Arquivo sem cabeçalho reconhecível; usando a ordem posicional das colunas."]
        first_line_number = 1
    else:
        sample_rows = all_rows[1:21]
        mapping, warnings = _resolve_columns(header, sample_rows)
        data_rows = all_rows[1:]
        first_line_number = 2

    for required in ("data", "valor"):
        if required not in mapping:
            raise CsvImportError(
                "Cabeçalho inválido: não foi possível identificar as colunas DATA e VALOR. "
                "Esperado: DATA;DESCRICAO;VALOR;TIPO;LOCAL;BANCO;CARTAO"
            )

    result = ParseResult(warnings=list(warnings))

    def cell(row: list[str], name: str) -> str:
        index = mapping.get(name)
        if index is None or index >= len(row):
            return ""
        return row[index]

    for line_number, row in enumerate(data_rows, start=first_line_number):
        movement_date = parse_date(cell(row, "data"))
        amount = parse_amount(cell(row, "valor"))
        if movement_date is None or amount is None:
            result.invalid_rows += 1
            if len(result.errors) < 10:
                motivo = "data inválida" if movement_date is None else "valor inválido"
                result.errors.append(f"Linha {line_number}: {motivo}.")
            continue

        description = _normalize_text(cell(row, "descricao"))
        expense_type = _normalize_text(cell(row, "tipo"), 120) or "SEM TIPO"
        local = _normalize_text(cell(row, "local"), 120)
        bank = _normalize_text(cell(row, "banco"), 120)
        card = _normalize_text(cell(row, "cartao"), 120)
        amount = abs(amount)
        source = "cartao" if card else "banco"

        result.rows.append(
            ParsedRow(
                movement_date=movement_date,
                description=description,
                amount=amount,
                expense_type=expense_type,
                local=local,
                bank=bank,
                card=card,
                source=source,
                fingerprint=build_fingerprint(
                    movement_date, description, amount, expense_type, local, bank, card, source
                ),
            )
        )

    return result
