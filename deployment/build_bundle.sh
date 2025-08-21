VERSION="NotForRelease"
SUFFIX="WeatherStation_Install_Bundle"
DBUS_OBJS_PATH="../ccs_dbus_objects"

if [ $# -eq 1 ]; then
    VERSION="$1"
fi

./make_manifest.sh $VERSION > ./manifest.xml

if [ ! -d "${DBUS_OBJS_PATH}" ]; then
    echo "Couldn't find ccs_dbus_objects directory at ${DBUS_OBJS_PATH}. BAILING OUT..."
    exit
fi

zip -r "${VERSION}_${SUFFIX}.zip" ./manifest.xml ../data_server.py ../bluez_dbus.py ../requirements.txt ../plugins/*.py ../system/ccsdata.service ../system/com.clearcreeksci.conf ../ccs_dbus_objects





