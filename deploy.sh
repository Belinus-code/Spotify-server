#!/bin/bash

set -e  # Beende bei Fehler

# 1. Baue das Paket
echo "Baue Paket..."
python -m build

# 2. Kopiere das Paket auf den Server
echo "Lade Paket hoch..."
scp dist/*.whl root@37.120.186.189:/home/root/deploy/

# 3. Führe Remote-Install & Restart aus
echo "Installiere & starte neu..."
ssh root@37.120.186.189 << EOF
  cd Spotify-server
  source venv/bin/activate
  pip install --upgrade --force-reinstall /home/root/deploy/*.whl
  systemctl restart spotify-server.service
EOF

echo "✅ Deployment abgeschlossen."
