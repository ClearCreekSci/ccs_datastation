#!/usr/bin/bash
UNZIP_DST="./unzip"
TOPLEVEL_DST="/opt/ccs"
VENV_DST="/opt/ccs/venv"
VENV_LIB_DIR="${VENV_DST}/lib"
SITE_DIR="site-packages"
DATASTATION_DST="/opt/ccs/DataStation"
SYSTEMD_SERVICE_DST="/etc/systemd/system"
DBUS_CONF_DST="/etc/dbus-1/system.d"

if [ $# -ne 1 ]; then
     echo "usage: $0 <path to install bundle>"
     exit
fi

if [ ! $EUID -eq 0 ]; then
    echo "Please run this install script as root"
    exit
fi

ping -c 1 google.com > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Unable to connect to internet. Installation failed."
    exit
fi

rm -rf ${UNZIP_DST}
mkdir ${UNZIP_DST}

unzip -q -d ${UNZIP_DST} $1

# Setup up the virtual environment first...
mkdir -p "${TOPLEVEL_DST}" 

echo "Creating Python virtual environment at ${VENV_DST}. This may take some time..."
python -m venv "${VENV_DST}"

echo "Installing required Python packages..."
source "${VENV_DST}/bin/activate"
pip install -r "${UNZIP_DST}/requirements.txt"

for entry in "${VENV_LIB_DIR}"/*
do
    PYTHON_VER=`basename "${entry}"`
done

cp -r "${UNZIP_DST}/ccs_dbus_objects" "${VENV_LIB_DIR}/${PYTHON_VER}/${SITE_DIR}/dbus_objects"

# Setup up the DataStation files...
mkdir -p "${DATASTATION_DST}"

echo "Copying DataStation files..."
cp "${UNZIP_DST}/data_server.py" "${DATASTATION_DST}"
cp "${UNZIP_DST}/bluez_dbus.py" "${DATASTATION_DST}"
cp -r  "${UNZIP_DST}/plugins" "${DATASTATION_DST}"
cp -r  "${UNZIP_DST}/manifest.xml" "${DATASTATION_DST}"
cp "${UNZIP_DST}/system/ccsdata.service" "${SYSTEMD_SERVICE_DST}"

echo "Creating ccsdata systemd service..."
systemctl daemon-reload
systemctl enable ccsdata.service
systemctl start ccsdata.service

# FIXME: Check for error on ccsdata startup and report it

echo "Configuring ccsdata dbus requirements..."
cp "${UNZIP_DST}/system/com.clearcreeksci.conf" "${DBUS_CONF_DST}"

rm -rf ${UNZIP_DST}

echo "Installation completed succesfully. Please reboot the device"


