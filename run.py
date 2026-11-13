"""Ponto de entrada da aplicação Money View."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
