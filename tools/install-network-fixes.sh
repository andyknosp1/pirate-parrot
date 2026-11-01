#!/bin/bash
# Make the Pi's network self-healing for a porch install. Run once with:
#   sudo bash tools/install-network-fixes.sh
# It (1) turns off Wi-Fi power saving, (2) installs a watchdog that restarts Wi-Fi when the
# router can't be reached, and reboots if that doesn't help, and (3) keeps system logs
# across reboots. Undo with: sudo bash tools/install-network-fixes.sh --remove
# Optional: add --2ghz to keep the Wi-Fi on 2.4 GHz. Use it if the log shows the Pi trying
# (and failing) to roam to 5 GHz: 2.4 GHz reaches much farther, e.g. out to a porch.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo"; exit 1; }

if [ "${1:-}" = "--remove" ]; then
    systemctl disable --now net-watchdog.timer 2>/dev/null || true
    rm -f /etc/systemd/system/net-watchdog.{service,timer} /usr/local/sbin/net-watchdog.sh \
          /etc/NetworkManager/conf.d/99-wifi-powersave-off.conf \
          /etc/systemd/journald.conf.d/99-persistent.conf
    systemctl daemon-reload
    echo "Removed. Reboot to finish."
    exit 0
fi

# 0. Optional: lock the current Wi-Fi connection to 2.4 GHz
if [ "${1:-}" = "--2ghz" ]; then
    CON=$(nmcli -t -f NAME,TYPE connection show --active | awk -F: '$2=="802-11-wireless" {print $1; exit}')
    if [ -n "$CON" ]; then
        nmcli connection modify "$CON" 802-11-wireless.band bg
        echo "Wi-Fi connection '$CON' locked to 2.4 GHz (takes effect at the next reconnect/reboot)."
    else
        echo "No active Wi-Fi connection found; skipping the 2.4 GHz lock."
    fi
fi

# 1. Wi-Fi power saving off (NetworkManager: 2 = disable)
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/99-wifi-powersave-off.conf <<'CONF'
[connection]
wifi.powersave = 2
CONF

# 2. Network watchdog, run every 30 seconds
cat > /usr/local/sbin/net-watchdog.sh <<'SH'
#!/bin/bash
# Ping the router. After 4 failed checks in a row (about 2 minutes) restart Wi-Fi; after 10
# (about 5 minutes) reboot, but never within 10 minutes of booting (avoids reboot loops if
# the router itself is down).
STATE=/run/net-watchdog.fails
LOG=/var/log/net-watchdog.log
GW=$(ip route show default | awk '/default/ {print $3; exit}')
fails=$(cat "$STATE" 2>/dev/null || echo 0)
if [ -n "$GW" ] && ping -c 2 -W 3 "$GW" >/dev/null 2>&1; then
    [ "$fails" -gt 0 ] && echo "$(date '+%F %T') network back after $fails failed checks" >> "$LOG"
    echo 0 > "$STATE"; exit 0
fi
fails=$((fails + 1)); echo "$fails" > "$STATE"
echo "$(date '+%F %T') router unreachable (check $fails, gateway '${GW:-none}')" >> "$LOG"
uptime_s=$(cut -d. -f1 /proc/uptime)
if [ "$fails" -ge 10 ] && [ "$uptime_s" -gt 600 ]; then
    echo "$(date '+%F %T') rebooting" >> "$LOG"; sync; systemctl reboot
elif [ $((fails % 4)) -eq 0 ]; then
    echo "$(date '+%F %T') restarting Wi-Fi" >> "$LOG"
    nmcli radio wifi off; sleep 3; nmcli radio wifi on; sleep 5
    # Turning the radio back on doesn't always reconnect by itself, so ask explicitly.
    nmcli --wait 20 device connect wlan0 >> "$LOG" 2>&1 || true
fi
SH
chmod 755 /usr/local/sbin/net-watchdog.sh

cat > /etc/systemd/system/net-watchdog.service <<'UNIT'
[Unit]
Description=Restart Wi-Fi (or reboot) if the router can't be reached

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/net-watchdog.sh
UNIT
cat > /etc/systemd/system/net-watchdog.timer <<'UNIT'
[Unit]
Description=Check the network every 30 seconds

[Timer]
OnBootSec=2min
OnUnitActiveSec=30s
AccuracySec=5s

[Install]
WantedBy=timers.target
UNIT

# 3. Keep the system journal across reboots (capped at 100 MB)
mkdir -p /etc/systemd/journald.conf.d /var/log/journal
cat > /etc/systemd/journald.conf.d/99-persistent.conf <<'CONF'
[Journal]
Storage=persistent
SystemMaxUse=100M
CONF
systemd-tmpfiles --create --prefix /var/log/journal

systemctl daemon-reload
systemctl enable --now net-watchdog.timer
systemctl restart systemd-journald
echo "Installed: Wi-Fi power saving off (after reboot), network watchdog, persistent logs."
echo "Watchdog log: /var/log/net-watchdog.log. Reboot now to apply the Wi-Fi setting: sudo reboot"
