# Money View

Aplicação local em Flask para importar **despesas** de cartão de crédito e de conta
bancária (CSV) e analisá-las com filtros, sempre exibindo o total do que está filtrado.

## Requisitos

- Python gerenciado por `pyenv` + `pyenv-virtualenv` (ambiente `money-view`)

## Como rodar

```bash
pyenv local money-view          # ativa o virtualenv do projeto
pip install -r requirements.txt
flask --app run run --debug
```

Acesse http://127.0.0.1:5000 — o banco SQLite é criado automaticamente em
`instance/money_view.db`.

## Páginas

- `/` — lista de despesas com filtros (período, **tipo de despesa**, origem, banco,
  cartão, busca textual, ordenação), cards de totais (total filtrado, lançamentos,
  ticket médio, maior despesa), resumo por tipo, total no rodapé da tabela e paginação.
- `/importar` — envio de um ou vários CSVs, formato esperado e histórico das
  importações (com opção de excluir uma importação e suas despesas).

## Formato do CSV

```text
DATA;DESCRICAO;VALOR;TIPO;LOCAL;BANCO;CARTAO
05/03/2025;SUPERMERCADO CENTRAL;152,90;ALIMENTACAO;SAO PAULO;ITAU;**** 1234
06/03/2025;UBER TRIP;28,45;TRANSPORTE;SAO PAULO;NUBANK;**** 5678
```

- `DATA`: `dd/mm/aaaa` (também aceita `aaaa-mm-dd` e variações).
- `DESCRICAO`: texto do lançamento (2ª coluna).
- `VALOR`: `1.234,56` ou `1234.56`; negativo/parênteses/sufixo `D` são aceitos e
  convertidos para o valor absoluto da despesa.
- `TIPO`: texto livre que classifica a despesa (`ALIMENTACAO`, `TRANSPORTE`,
  `LAZER`, …). Cada valor distinto vira uma opção do combo de filtro.
- `CARTAO` preenchido indica origem “Cartão”, vazio indica “Banco”.
- Codificação detectada automaticamente (UTF-8 ou Windows-1252).
- Linhas idênticas já importadas são ignoradas (fingerprint em SHA-256).

### Tolerância na leitura do cabeçalho

A resolução das colunas tenta, nesta ordem: nome exato/sinônimos (`HISTORICO`,
`CATEGORIA`, `DESCRITIVO`, `DT`, `VLR`…), conteúdo da coluna (data/valor) e, por
fim, a posição do layout documentado. Arquivos sem cabeçalho também são aceitos.
Quando alguma coluna é resolvida por posição, a importação exibe um aviso no
histórico.

## Configuração

Copie `.env.example` para `.env` para definir `SECRET_KEY` e, se quiser,
`DATABASE_URL`.

## Observação sobre esquema

O banco é criado por `db.create_all()`. Se um banco de uma versão anterior
(campo `direction`) for encontrado, as tabelas são recriadas automaticamente e os
CSVs precisam ser reimportados — a origem dos dados são os próprios arquivos.
