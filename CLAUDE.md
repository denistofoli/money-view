# CLAUDE.md - Diretivas e Arquitetura do Projeto

Este arquivo fornece instruções e contexto essenciais para o Claude Code operar neste repositório. Siga rigorosamente todas as diretrizes abaixo ao gerar, refatorar ou depurar código.

## 1. Ambiente e Gestão de Dependências (Python & pyenv)

* **Gerenciador de Versão e Ambientes:** Este projeto utiliza exclusivamente o `pyenv` e o plugin `pyenv-virtualenv` para gestão do interpretador e dos ambientes virtuais.
* **Versão do Python:** Utilize sempre a **última versão estável instalada localmente** via `pyenv`.
* **Padrão do Virtualenv:** O ambiente virtual deve ser criado e vinculado ao diretório utilizando o mesmo nome da pasta raiz do projeto:
  * Criação: `pyenv virtualenv <versao_mais_recente> <nome_da_pasta>` (ou `pyenv virtualenv <nome_da_pasta>` utilizando a versão global/ativa mais recente).
  * Ativação local: `pyenv local <nome_da_pasta>` (gerando o arquivo `.python-version` apontando para o virtualenv).
* **Verificação:** Antes de executar scripts, instalar pacotes ou sugerir comandos de terminal, verifique o ambiente ativo (`pyenv version` / `pyenv virtualenvs` / `which python`). Nunca crie pastas `venv` ou `.venv` locais dentro do repositório, pois o ambiente é gerenciado centralmente pelo `pyenv`.
* **Dependências:** Mantenha todas as bibliotecas instaladas devidamente registradas no arquivo `requirements.txt`.

## 2. Stack Tecnológica Obrigatória

* **Backend:** Python com microframework **Flask** (arquitetura modular utilizando *Blueprints* e padrão *Application Factory* `create_app()`).
* **Banco de Dados:** **SQLite** (arquivo local `.db` ou `.sqlite3` na pasta `instance/`, devidamente ignorado no `.gitignore`).
  * Utilize SQLAlchemy (Flask-SQLAlchemy) com Flask-Migrate para gerenciamento de esquemas, ou `sqlite3` nativo caso o projeto seja estritamente minimalista. Dê preferência a consultas parametrizadas para evitar *SQL Injection*.
* **Frontend & Estilização:** Templates **Jinja2** estilizados exclusivamente com **Bootstrap (última versão estável - v5.3+)**.
  * Utilize os CDNs oficiais mais recentes do Bootstrap (CSS e JS Bundle com Popper) no template base (`base.html`), ou arquivos estáticos locais se o projeto exigir funcionamento offline.
  * Priorize o uso de classes utilitárias nativas do Bootstrap 5 (Grid system, Flex, Spacing, Componentes) e evite escrever CSS customizado desnecessário.

## 3. Estrutura de Diretórios Esperada

Mantenha a organização padrão de projetos Flask:

```text
/
├── instance/               # Banco de dados SQLite e configs locais (não versionado)
├── app/
│   ├── __init__.py         # Application Factory (create_app)
│   ├── models.py           # Modelos do banco de dados SQLite
│   ├── routes/             # Blueprints organizando as rotas
│   ├── static/             # CSS customizado mínimo, JS e imagens
│   └── templates/          # Templates Jinja2
│       ├── base.html       # Layout mestre com imports do Bootstrap mais recente
│       └── ...
├── .python-version         # Nome do virtualenv definido via pyenv local
├── requirements.txt        # Dependências do projeto
├── run.py                  # Ponto de entrada da aplicação
└── CLAUDE.md               # Este arquivo de diretivas
```

## 4. Boas Práticas de Desenvolvimento e Código

* **Qualidade de Código:** Siga a PEP 8. Utilize *Type Hints* em funções e métodos sempre que possível.
* **Segurança:**
  * Nunca faça *hardcode* de `SECRET_KEY` ou credenciais; utilize variáveis de ambiente (`python-dotenv`).
  * Proteja formulários contra CSRF (utilize `Flask-WTF` quando aplicável).
* **Templates e UI/UX:**
  * Todo template HTML deve herdar de `base.html` usando `{% extends 'base.html' %}`.
  * Garanta responsividade (*mobile-first*) utilizando os containers e breakpoints padrão do Bootstrap.
  * Utilize *Flash Messages* do Flask estilizadas com os componentes `alert` e `alert-dismissible` do Bootstrap para feedback ao usuário.

## 5. Comandos Úteis para o Agente

Ao configurar, testar ou rodar a aplicação para validação, utilize:

* **Verificar versões e ambientes:** `pyenv versions` e `pyenv virtualenvs`
* **Configurar ambiente (se inexistente):** `pyenv virtualenv $(basename "$PWD")` seguido de `pyenv local $(basename "$PWD")`
* **Instalar dependências:** `pip install -r requirements.txt`
* **Iniciar servidor de desenvolvimento:** `flask --app run run --debug`