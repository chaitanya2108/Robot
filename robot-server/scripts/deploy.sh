#!/bin/bash
# Run from a Linux/macOS machine:  robot-server/scripts/deploy.sh [robot-ip]
set -e
ROBOT=${1:-192.168.1.105}
SRC="$(cd "$(dirname "$0")/.." && pwd)"
tar -C "$SRC" --exclude=build --exclude=__pycache__ -cf - . \
  | ssh "hiwonder@${ROBOT}" 'mkdir -p ~/robot_app/server && tar xf - -C ~/robot_app/server && bash ~/robot_app/server/scripts/install.sh'
