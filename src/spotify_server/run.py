"""Entry point für die Flask-Anwendung."""

# pylint: disable=E0611
from app import create_app

# Erstelle die Anwendungsinstanz mit der Factory
app = create_app()

if __name__ == "__main__":
    # Starte den Flask-Entwicklungsserver
    # debug=True sorgt für automatische Neustarts bei Code-Änderungen und zeigt Fehler im Browser an.
    app.run(debug=True)
