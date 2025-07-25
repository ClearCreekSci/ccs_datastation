# ccs_datastation
Provides a Bluetooth Gatt Service to read data from attached sensors. Designed to run on a Raspberry Pi. We use either the Pi Zero with wireless or the Pi Zero 2 with wireless.

# dbus_objects
The dbus_objects directory contains a forked version of 

# deployment directory
The deployment directory contains two scripts, one to create the zipped installation bundle from the development directory and one to unzip the bundle and create the necessary system artifacts on the target. In order for the scripts to work correctly, the dbus_objects and plugins directories must be populated.

# plugins directory
For an ordinary installation, the plugins directory contains Python scripts that read sensor data and communicate it back to the data station. We currently offer the following plugins:

* [Adafruit BME280][https://github.com/ClearCreekSci/bme280_ccs_plugin]


