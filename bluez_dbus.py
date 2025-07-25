"""
    bluez_dbus.py
    Copyright (C) 2025 Clear Creek Scientific 

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

*********************************
    Requires the jeepney library (available on PyPi)

*********************************

    This file contains a modified version of the auto-generated DBus bindings 
    created by jeepney version 0.8.0 with the command: 

    > python -m jeepney.bindgen --name org.bluez --path /org/bluez/hci0 --bus SYSTEM

    Object path: /org/bluez/<adapter name (usually hci0)>
    Bus name   : org.bluez
"""

from jeepney.wrappers import new_method_call
from jeepney.wrappers import MessageGenerator
from jeepney.wrappers import Properties

BLUEZ_PATH                       = '/org/bluez'
BLUEZ_BUS_NAME                   = 'org.bluez'
BLUEZ_ADAPTER_INTERFACE          = 'org.bluez.Adapter1'
LE_ADVERTISING_INTERFACE         = 'org.bluez.LEAdvertisement1'
LE_ADVERTISING_MANAGER_INTERFACE = 'org.bluez.LEAdvertisingManager1'
LE_AGENT_INTERFACE               = 'org.bluez.Agent1'
LE_AGENT_MANAGER_INTERFACE       = 'org.bluez.AgentManager1'
GATT_MANAGER_INTERFACE           = 'org.bluez.GattManager1'
GATT_SERVICE_INTERFACE           = 'org.bluez.GattService1'
GATT_SERVICE_PATH                = '/org/bluez/GattService1'
GATT_CHARACTERISTIC_INTERFACE    = 'org.bluez.GattCharacteristic1'
DBUS_PATH                        = '/org/freedesktop/DBus'
DBUS_NAME                        = 'org.freedesktop.DBus'
DBUS_INTERFACE                   = 'org.freedesktop.DBus'
DBUS_PROPERTIES_INTERFACE        = 'org.freedesktop.DBus.Properties'
DBUS_OBJECT_MANAGER_INTERFACE    = 'org.freedesktop.DBus.ObjectManager'
DBUS_PEER_INTERFACE              = 'org.freedesktop.DBus.Peer'
DBUS_INTROSPECTABLE_INTERFACE    = 'org.freedesktop.DBus.Instrospectable'

class Adapter(MessageGenerator):
    interface = 'org.bluez.Adapter1'

    def __init__(self,name):
        super().__init__(object_path='/org/bluez/' + name,bus_name='org.bluez')

    def StartDiscovery(self):
        return new_method_call(self, 'StartDiscovery')

    def SetDiscoveryFilter(self, properties):
        return new_method_call(self, 'SetDiscoveryFilter', 'a{sv}',(properties,))

    def StopDiscovery(self):
        return new_method_call(self, 'StopDiscovery')

    def RemoveDevice(self, device):
        return new_method_call(self, 'RemoveDevice', 'o',(device,))

    def GetDiscoveryFilters(self):
        return new_method_call(self, 'GetDiscoveryFilters')

    def GetDiscoverable(self):
        props = Properties(self)
        return props.get('Discoverable')

    def SetDiscoverable(self,v):
        props = Properties(self)
        return props.set('Discoverable','b',v)

    def GetPowered(self):
        props = Properties(self)
        return props.get('Powered')

    def SetPowered(self,v):
        props = Properties(self)
        return props.set('Powered','b',v)

class GattManager(MessageGenerator):
    interface = 'org.bluez.GattManager1'

    def __init__(self, object_path='/org/bluez/hci0',
                 bus_name='org.bluez'):
        super().__init__(object_path=object_path, bus_name=bus_name)

    def RegisterApplication(self, application, options):
        return new_method_call(self, 'RegisterApplication', 'oa{sv}',
                               (application, options))

    def UnregisterApplication(self, application):
        return new_method_call(self, 'UnregisterApplication', 'o',
                               (application,))

class LEAdvertisingManager(MessageGenerator):
    interface = 'org.bluez.LEAdvertisingManager1'

    def __init__(self, object_path='/org/bluez/hci0',
                 bus_name='org.bluez'):
        super().__init__(object_path=object_path, bus_name=bus_name)

    def RegisterAdvertisement(self, advertisement, options):
        return new_method_call(self, 'RegisterAdvertisement', 'oa{sv}',
                               (advertisement.default_interface_root, options))

    def UnregisterAdvertisement(self, service):
        return new_method_call(self, 'UnregisterAdvertisement', 'o',
                               (service))


