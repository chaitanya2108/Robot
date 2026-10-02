#!/bin/bash
# Run ON THE ROBOT from ~/robot_app/server:  bash scripts/install.sh
# Installs Python deps, builds the camera bridge, creates the config/token and
# installs + starts the systemd service. Safe to run again after updates.
set -e
cd "$(dirname "$0")/.."
SERVER_DIR=$(pwd)

echo "==> Python dependencies"
python3 -m pip install --user -q -r requirements.txt

echo "==> Building camera bridge"
mkdir -p camera_bridge/build
(cd camera_bridge/build && cmake .. -DCMAKE_BUILD_TYPE=Release > /dev/null && make -j2 2>&1 | tail -1)

echo "==> Config"
python3 -m robot_server --show-token > /dev/null   # creates ~/robot_app/config.yaml with a token if missing

echo "==> systemd service"
sudo cp systemd/robot-server.service /etc/systemd/system/robot-server.service
sudo sed -i "s#WorkingDirectory=.*#WorkingDirectory=${SERVER_DIR}#" /etc/systemd/system/robot-server.service
sudo systemctl daemon-reload
sudo systemctl enable robot-server.service > /dev/null 2>&1
sudo systemctl restart robot-server.service
sleep 3
systemctl --no-pager --lines=0 status robot-server.service | head -3

IP=$(hostname -I | awk '{print $1}')
echo
echo "Robot server is running."
echo "  Address: ${IP}:8765"
echo "  Token:   $(python3 -m robot_server --show-token)"
