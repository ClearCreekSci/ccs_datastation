VERSION="NotForRelease"
SUFFIX="DataStation_Install_Bundle"
DBUS_OBJS_PATH="../dbus_objects"

if [ $# -eq 1 ]; then
    VERSION="$1"
fi

if [ ! -d "${DBUS_OBJS_PATH}" ]; then
    echo "Couldn't find dbus_objects directory at ${DBUS_OBJS_PATH}. BAILING OUT..."
    exit
fi

zip -r "${VERSION}_${SUFFIX}.zip" ../data_server.py ../bluez_dbus.py ../requirements.txt ../plugins/bme280.py ../system/ccsdata.service ../system/com.clearcreeksci.conf ../dbus_objects





