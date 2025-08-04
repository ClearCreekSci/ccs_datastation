TOPLEVEL_DST="/opt/ccs"
SYSTEMD_SERVICE_DST="/etc/systemd/system"
DBUS_CONF_DST="/etc/dbus-1/system.d"

echo "Removing ccsdata systemd service..."
systemctl stop ccsdata.service
systemctl disable ccsdata.service
systemctl daemon-reload
rm "${SYSTEMD_SERVICE_DST}/ccsdata.service"

echo "Removing ccsdata dbus components..."
rm "${DBUS_CONF_DST}/com.clearcreeksci.conf"

echo "Removing ccsdata files"
rm -rf "${TOPLEVEL_DST}" 

echo "Uninstall complete"

