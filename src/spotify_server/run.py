"""Entry point für die Flask-Anwendung."""

# pylint: disable=E0611
from spotify_server.app import create_app

# Erstelle die Anwendungsinstanz mit der Factory
app = create_app()

if __name__ == "__main__":
    # Starte den Flask-Entwicklungsserver
    # debug=True sorgt für automatische Neustarts bei Code-Änderungen und zeigt Fehler im Browser an.
    app.run(debug=True)


def main():
    """
    Der Haupteinstiegspunkt für das Skript.
    Startet den Flask-Entwicklungsserver.
    Für die Produktion würdest du hier einen WSGI-Server wie gunicorn starten.
    """
    # Host='0.0.0.0' macht den Server im lokalen Netzwerk erreichbar
    app.run(host="0.0.0.0", port=5000, debug=False)
