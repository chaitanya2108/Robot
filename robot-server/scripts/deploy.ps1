# Run on your Windows PC from the Robot folder:
#   powershell -ExecutionPolicy Bypass -File robot-server\scripts\deploy.ps1 [-RobotIp 192.168.1.105]
# Copies robot-server to the robot and runs the installer there.
# You will be asked for the robot password (hiwonder) twice.
param([string]$RobotIp = "192.168.1.105", [string]$User = "hiwonder")
$ErrorActionPreference = "Stop"
$src = Split-Path -Parent $PSScriptRoot
Write-Host "Copying $src to ${User}@${RobotIp}:~/robot_app/server"
tar -C "$src" --exclude=build --exclude=__pycache__ -cf "$env:TEMP\robot-server.tar" .
scp "$env:TEMP\robot-server.tar" "${User}@${RobotIp}:/tmp/robot-server.tar"
ssh "${User}@${RobotIp}" "mkdir -p ~/robot_app/server && tar xf /tmp/robot-server.tar -C ~/robot_app/server && rm /tmp/robot-server.tar && bash ~/robot_app/server/scripts/install.sh"
