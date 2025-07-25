"""
    data_server.py
    Presents a Bluetooth Gatt Service to read data from various sensors

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
    Requires various Python packages. See the requirements.txt file.

    Uses a forked version of dbus-objects available at  ...

"""


import os
import argparse
import trio
import logging
import platform
import xml.etree.ElementTree as et

from jeepney import DBusAddress
from jeepney import new_method_call
from jeepney.wrappers import Introspectable
from jeepney.wrappers import DBusErrorResponse
import jeepney.io.trio

import dbus_objects
import dbus_objects.types
import dbus_objects.integration.jeepney

from typing import List
from typing import Dict
from typing import Any
from typing import Optional
from collections import defaultdict

from importlib import import_module

import bluez_dbus
from bluez_dbus import Adapter
from bluez_dbus import DBUS_NAME 
from bluez_dbus import DBUS_PATH 
from bluez_dbus import DBUS_INTERFACE 
from bluez_dbus import BLUEZ_PATH
from bluez_dbus import BLUEZ_BUS_NAME
from bluez_dbus import BLUEZ_ADAPTER_INTERFACE
from bluez_dbus import DBUS_PROPERTIES_INTERFACE
from bluez_dbus import DBUS_OBJECT_MANAGER_INTERFACE
from bluez_dbus import GATT_CHARACTERISTIC_INTERFACE
from bluez_dbus import GATT_SERVICE_INTERFACE
from bluez_dbus import GATT_SERVICE_PATH
from bluez_dbus import GATT_MANAGER_INTERFACE
from bluez_dbus import LE_ADVERTISING_INTERFACE
from bluez_dbus import LE_ADVERTISING_MANAGER_INTERFACE
from bluez_dbus import LE_AGENT_INTERFACE
from bluez_dbus import LE_AGENT_MANAGER_INTERFACE
from bluez_dbus import DBUS_INTROSPECTABLE_INTERFACE
from bluez_dbus import DBUS_PEER_INTERFACE

ADVERT_LABEL                        = 'advertisement'
AGENT_LABEL                         = 'agent'
APP_LABEL                           = 'application'
HUMIDITY_LABEL                      = 'humidity'
PRESSURE_LABEL                      = 'pressure'
TEMPERATURE_LABEL                   = 'temperature'

CCS_ROOT                            = '/com/clearcreeksci'
CCS_NAME                            = 'com.clearcreeksci'
CCS_DATA_ROOT                       = '/com/clearcreeksci/data'
CCS_DATA_NAME                       = 'com.clearcreeksci.data'
CCS_ADVERT_ROOT                     = '/com/clearcreeksci/' + ADVERT_LABEL
CCS_ADVERT_NAME                     = 'com.clearcreeksci.' + ADVERT_LABEL 
CCS_AGENT_ROOT                      = '/com/clearcreeksci/' + AGENT_LABEL
CCS_AGENT_NAME                      = 'com.clearcreeksci.' + AGENT_LABEL

CCS_ADVERT_UUID                     = 'a0ce0100-3bbf-11ee-89eb-00e04c400cc5'
CCS_AGENT_UUID                      = 'a0ce0101-3bbf-11ee-89eb-00e04c400cc5'
CCS_DATA_SERVICE_UUID               = 'a0ce0200-3bbf-11ee-89eb-00e04c400cc5'
CCS_SERVICE_ID_UUID                 = 'a0ce0201-3bbf-11ee-89eb-00e04c400cc5'
CCS_AIR_TEMPERATURE_UUID            = 'a0ce0210-3bbf-11ee-89eb-00e04c400cc5'
CCS_HUMIDITY_UUID                   = 'a0ce0211-3bbf-11ee-89eb-00e04c400cc5'
CCS_AIR_PRESSURE_UUID               = 'a0ce0212-3bbf-11ee-89eb-00e04c400cc5'


SHARED_OBJECT_DIR                   = 'plugins'

DEFAULT_UPDATE_SECONDS              = 10

g_hci = None

logging.basicConfig(filename='/tmp/data_station.log')
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class NoBluetoothAdapter(Exception):
    pass

# Based on dbus_objects.integration.jeepney.TrioDBusServer
class CcsServer(dbus_objects.integration.jeepney._JeepneyServerBase):

    def __init__(self,bus,name) -> None:
        super().__init__(bus,name)
        self.open = False
        self.application = None
        self.application_registered = False
        self.agent = None
        self.plugins = None
        self.most_recent_data = None
        self.dbus_ready = False
        self.update_seconds = DEFAULT_UPDATE_SECONDS
        self.load_plugins()
        self._logger = logging.getLogger(self.__class__.__name__)

    # dbus_objects method for an async initialization function
    @classmethod
    async def new(cls,bus: str,name: str):
        inst = cls(bus,name)
        await inst._conn_start()
        inst.register_dbus_advertisement()
        inst.register_dbus_agent()
        return inst

    async def _conn_start(self) -> None:
        if False == self.open:
            print(self._name)
            self._conn = await jeepney.io.trio.open_dbus_connection(self._bus)
            async with self._conn.router() as router:
                try:
                    bus_proxy = jeepney.io.trio.Proxy(jeepney.message_bus,router)
                    await bus_proxy.RequestName(self._name)
                    self.open = True
                except DBusErrorResponse as e:
                    log.error('[_conn_start] Error opening router: ' + str(e))

    async def _handle_msg(self,msg: jeepney.Message) -> None:
        log.debug('[_handle_msg] msg: ' + str(msg))
        return_msg = self._jeepney_handle_msg(msg)
        if None is not return_msg:
            log.debug('[_handle_msg] returning msg: ' + str(return_msg))
            await self._conn.send(return_msg)

    async def emit_signal(self,signal: dbus_objects._DBusSignal,path: str,body: Any) -> None:
        await self._conn.send_message(self._get_signal_msg(signal,path,body))

    async def close(self) -> None:
        if self.open: 
            self.open = False

    async def rx(self) -> None:
        while True == self.open:
            try:
                msg = await self._conn.receive()
            except ConnectionResetError:
                self.open = False
                await self._conn_start()
            else:
                await self._handle_msg(msg)

    async def register_bluez_agent(self) -> None:
        path = bluez_dbus.BLUEZ_PATH
        name = bluez_dbus.BLUEZ_BUS_NAME

        while False == self.application_registered:
            await trio.sleep(1)

        agent_name = CCS_AGENT_ROOT
        log.info('Registering agent at: ' + str(agent_name))
        addr = DBusAddress(path,bus_name=name,interface=bluez_dbus.LE_AGENT_MANAGER_INTERFACE)
        msg = new_method_call(addr,'RegisterAgent','os',(agent_name,"NoInputNoOutput"))
        async with self._conn.router() as rtr:
            await rtr.send(msg);


    async def register_bluez_application(self) -> None:
        path = bluez_dbus.BLUEZ_PATH + '/' + g_hci
        name = bluez_dbus.BLUEZ_BUS_NAME
        addr = DBusAddress(path,bus_name=name,interface=bluez_dbus.GATT_MANAGER_INTERFACE)

        log.info('Registering application at ' + CCS_DATA_ROOT)
        msg = new_method_call(addr,'RegisterApplication','oa{sv}',(CCS_DATA_ROOT,{}))
        async with self._conn.router() as rtr:
            await rtr.send(msg);
        self.application_registered = True

    async def register_bluez_advertisement(self) -> None:
        path = bluez_dbus.BLUEZ_PATH
        name = bluez_dbus.BLUEZ_BUS_NAME

        while False == self.application_registered:
            await trio.sleep(1)

        # Setting the DiscoverableTimeout to 0 disables the timeout
        #addr = DBusAddress(path,bus_name=name,interface=bluez_dbus.DBUS_PROPERTIES_INTERFACE)
        #msg = new_method_call(addr,'Get','ssv',(bluez_dbus.BLUEZ_ADAPTER_INTERFACE,'DiscoverableTimeout',('i',0)))

        ad_name = CCS_ADVERT_ROOT
        log.info('Registering advertisement at: ' + str(ad_name))
        path = bluez_dbus.BLUEZ_PATH + '/' + g_hci
        addr = DBusAddress(path,bus_name=name,interface=bluez_dbus.LE_ADVERTISING_MANAGER_INTERFACE)
        msg = new_method_call(addr,'RegisterAdvertisement','oa{sv}',(ad_name,{}))
        async with self._conn.router() as rtr:
            await rtr.send(msg);


    async def collect_latest(self) -> None:
        for plugin in self.plugins:
            data = plugin.get_current_values()
            for x in data:
                if 2 == len(x):
                    self.most_recent_data[x[0]] = x[1]

    async def collect_data(self) -> None:
        await trio.sleep(5)
        while True == self.open:
            await trio.sleep(self.update_seconds)
            await self.collect_latest()
        
    async def listen(self) -> None:
        self._log_topology()
        try:
            async with trio.open_nursery() as nursery:
                nursery.start_soon(self.rx)
                nursery.start_soon(self.register_bluez_application)
                nursery.start_soon(self.register_bluez_agent)
                nursery.start_soon(self.register_bluez_advertisement)
                nursery.start_soon(self.collect_data)
        except* KeyboardInterrupt:
            await self.close()
            log.info('bye')

    def register_dbus_agent(self) -> None:
        self.agent = Agent()
        self.register_object(CCS_AGENT_ROOT,self.agent)

    def register_dbus_advertisement(self) -> None:
        self.advert = Advertisement()
        self.register_object(CCS_ADVERT_ROOT,self.advert)

    def load_plugins(self):
        self.plugins = list()
        self.most_recent_data = dict()

        if False == os.path.exists(SHARED_OBJECT_DIR):
            os.mkdir(SHARED_OBJECT_DIR,mode=0o755)
        files = os.listdir(SHARED_OBJECT_DIR)
        for f in files:
            if f.endswith('.py'):
                if '__init__.py' != f:
                    f = f[:-3]
                    name = SHARED_OBJECT_DIR + '.' + f
                    try:
                        mod = import_module(name)
                        obj = mod.load()
                        self.plugins.append(obj)
                    except Exception:
                        log.error('Failed to load plugin: ' + name)
                        pass

    def get_collected_data(self,uuid) -> str:
        rv = None
        if uuid in self.most_recent_data:
            rv = self.most_recent_data[uuid]
        return rv

class Sensor(dbus_objects.DBusObject):

    def __init__(self,uuid,obj_name=None,server = None):
        super().__init__(name=obj_name,default_interface_root=CCS_DATA_ROOT)
        self.value = bytes() 
        self.characteristic_name = obj_name
        self.uuid = uuid
        self.server = server
        # Value chosen empirically
        self.mtu = 517

    @dbus_objects.dbus_method(interface=DBUS_PROPERTIES_INTERFACE,name='Set')
    def SetProperties(self,interface_name: str,property_name: str,value: dbus_objects.types.Variant):
        log.debug('[SetProperties] interface: ' + interface_name + ', property_name: ' + property_name + ', value = ' + str(value))
        

    # I'm not sure why dbus-objects requires these two Properties interfaces, rather
    # than relying on the @dbus_objects.dbus_property decorated functions, but if
    # I don't add them, then I get an error trying to query properties
    @dbus_objects.dbus_method(interface=DBUS_PROPERTIES_INTERFACE,name='Get')
    def GetProperties(self,interface_name: str,property_name: str) -> dbus_objects.types.Variant:
        rv = None
        if GATT_CHARACTERISTIC_INTERFACE == interface_name:
            if 'UUID' == property_name:
                rv = 's',self.get_uuid()
            elif 'Service' == property_name:
                rv = 'o',self.get_service_name()
            elif 'Flags' == property_name:
                rv = 'as',self.get_flags()
            elif 'MTU' == property_name:
                rv = 'q',self.get_mtu()
        return rv 

    @dbus_objects.dbus_method(interface=DBUS_PROPERTIES_INTERFACE,name='GetAll')
    def GetAllProperties(self,interface_name: str) -> Dict[str,dbus_objects.types.Variant]:
        return self.get_all_properties(interface_name)

    @dbus_objects.dbus_property(interface=GATT_CHARACTERISTIC_INTERFACE)
    def UUID(self) -> str:
        return self.get_uuid()

    @dbus_objects.dbus_property(interface=GATT_CHARACTERISTIC_INTERFACE)
    def Service(self) -> str:
        return CCS_DATA_ROOT 

    @dbus_objects.dbus_property(interface=GATT_CHARACTERISTIC_INTERFACE)
    def Flags(self) -> list[str]:
        return self.GetFlags()

    @dbus_objects.dbus_method(interface=GATT_CHARACTERISTIC_INTERFACE,name='ReadValue')
    def ReadValue(self,options: Dict[str,dbus_objects.types.Variant]) -> bytes:
        if None is not self.server:
            self.value = self.server.get_collected_data(self.get_uuid())
            if None is not self.value:
                return self.value.encode('utf-8')
        return bytes()

    def hex_value_of_char(self,c):
        rv = 0
        if c >= '0' and c <= '9':
            rv = ord(c) - ord('0')
        elif c >= 'a' and c <= 'f':
            rv = ord(c) - ord('a') + 10
        elif c >= 'A' and c <= 'F':
            rv = ord(c) - ord('A') + 10
        return rv
         
    # This assumes that buf contains a hex string
    def file_bytes_to_value_bytes(self,buf):
        rv = list()
        q = len(buf) % 2
        if q == 0:
            idx = 0
            while idx < (len(buf)-1):
                 x = self.HexValueOfChar(buf[idx]) << 4
                 idx += 1
                 x += self.HexValueOfChar(buf[idx])
                 idx += 1
                 rv.append(x)
        return rv

    def get_service_name(self):
        return CCS_DATA_ROOT

    def get_flags(self):
        return ['read']

    def get_uuid(self):
        return self.uuid

    def get_mtu(self):
        return self.mtu

    def set_value(self,new_value):
        if isinstance(new_value,list):
            if len(new_value) > 0:
                if isinstance(new_value[0],int):
                    self.value = new_value

    def get_all_properties(self,interface_name):
        rv = dict()
        if GATT_CHARACTERISTIC_INTERFACE == interface_name:
            rv['UUID'] = ('s',self.get_uuid())
            rv['Service'] = ('o',self.get_service_name())
            rv['Flags'] = ('as',self.get_flags())
            rv['MTU'] = ('q',self.get_mtu())
        return rv 

    def get_path(self):
        return self.default_interface_root + '/' + self.characteristic_name

    def get_all_interfaces(self):
        rv = dict()
        #rv[DBUS_PEER_INTERFACE] = {}
        #rv[DBUS_PROPERTIES_INTERFACE] = {}
        #rv[DBUS_INTROSPECTABLE_INTERFACE] = {}
        rv[GATT_CHARACTERISTIC_INTERFACE] = self.GetAllProperties(GATT_CHARACTERISTIC_INTERFACE)
        return rv

class CcsData(dbus_objects.DBusObject):

    def __init__(self,uuid='',is_primary=True):
        super().__init__(default_interface_root=CCS_DATA_ROOT)
        self.primary = is_primary
        self.uuid = uuid
        self.server = None
        self.sensors = list()

    @dbus_objects.dbus_method(interface=DBUS_OBJECT_MANAGER_INTERFACE,name='GetManagedObjects')
    def GetManagedObjects(self) -> Dict[dbus_objects.types.ObjectPath,Dict[str,Dict[str,dbus_objects.types.Variant]]]:
        rv = self.get_all_interfaces()
        log.debug('[CcsData:get_managed_objects] rv = ' + str(rv) + '\n')
        return rv

    @dbus_objects.dbus_method(interface=DBUS_PROPERTIES_INTERFACE,name='GetAll')
    def GetAllProperties(self,interface_name: str) -> Dict[str,dbus_objects.types.Variant]:
        rv = self.get_all_properties(interface_name)
        log.debug('[CcsData:get_all_properties] rv = ' + str(rv) + '\n')
        return rv 

    @dbus_objects.dbus_method(interface=DBUS_PROPERTIES_INTERFACE,name='Get')
    def GetProperties(self,interface_name: str,property_name: str) -> dbus_objects.types.Variant:
        rv = None
        if GATT_SERVICE_INTERFACE == interface_name:
            if 'UUID' == property_name:
                rv = 's',self.get_uuid()
            elif 'Primary' == property_name:
                rv = 'b',self.is_primary()
        return rv 

    @dbus_objects.dbus_property(interface=GATT_SERVICE_INTERFACE)
    def UUID(self) -> str:
        return self.get_uuid()

    @dbus_objects.dbus_property(interface=GATT_SERVICE_INTERFACE)
    def Primary(self) -> int:
        return self.is_primary()

    def is_primary(self):
        return self.primary

    def get_uuid(self):
        return self.uuid

    def get_all_properties(self,interface_name):
        rv = dict()
        if GATT_SERVICE_INTERFACE == interface_name:
            rv['UUID'] = ('s',self.get_uuid())
            rv['Primary'] = ('b',self.is_primary())
        return rv 

    def add_sensor(self,v):
        self.sensors.append(v)

    def get_all_interfaces(self):
        rv = dict()
        #rv[DBUS_PEER_INTERFACE] = {}
        #rv[DBUS_PROPERTIES_INTERFACE] = {}
        inner = dict()
        inner[DBUS_INTROSPECTABLE_INTERFACE] = {}
        inner[GATT_SERVICE_INTERFACE] = self.GetAllProperties(GATT_SERVICE_INTERFACE)
        rv[CCS_DATA_ROOT] = inner 
        for sensor in self.sensors:
            rv[sensor.get_path()] = sensor.get_all_interfaces()
        return rv

class Advertisement(dbus_objects.DBusObject):

    def __init__(self):
        super().__init__(default_interface_root=CCS_ADVERT_ROOT)
        self.type = 'peripheral'
        self.discoverable = True
        self.uuid = CCS_ADVERT_UUID
        self.timeout = 120
        self.tx_power = -3

    @dbus_objects.dbus_method(interface=DBUS_OBJECT_MANAGER_INTERFACE,name='GetManagedObjects')
    def GetManagedObjects(self) -> Dict[str,Dict[str,Dict[str,dbus_objects.types.Variant]]]:
        rv = self.get_all_interfaces()
        #log.debug('[Advertisement:get_managed_objects] rv = ' + str(rv) + '\n')
        return rv

    @dbus_objects.dbus_method(interface=bluez_dbus.DBUS_PROPERTIES_INTERFACE,name='GetAll')
    def GetAllProperties(self,interface_name: str) -> Dict[str,dbus_objects.types.Variant]:
        return self.get_all_properties(interface_name)

    @dbus_objects.dbus_method(interface=bluez_dbus.DBUS_PROPERTIES_INTERFACE,name='Get')
    def GetProperties(self,interface_name: str,property_name: str) -> dbus_objects.types.Variant:
        rv = None
        if bluez_dbus.LE_ADVERTISING_INTERFACE == interface_name:
            if 'Type' == property_name:
                rv = 's',self.GetType()
            elif 'Discoverable' == property_name:
                rv = 'b',self.GetDiscoverable()
            #elif 'DiscoverableTimeout' == property_name:
            #    rv = 'q',self.GetDiscoverableTimeout()
            elif 'ServiceUUIDs' == property_name:
                rv = 'as',self.GetServiceUUIDs()
            #elif 'SolicitUUIDs' == property_name:
            #    rv = 'as',self.GetSolicitUUIDs()
            #elif 'ManufacturerData' == property_name:
            #    rv = 'a{qay}',self.GetManufacturerData()
            #elif 'ServiceData' == property_name:
            #    rv = 'a{qay}',self.GetServiceData()
            #elif 'Data' == property_name:
            #    rv = 'a{qay}',self.GetData()
            #elif 'Includes' == property_name:
            #    rv = 'as',self.GetIncludes()
            elif 'LocalName' == property_name:
                rv = 's',self.GetLocalName()
            #elif 'Appearance' == property_name:
            #    rv = 'q',self.GetAppearance()
            #elif 'Timeout' == property_name:
            #    rv = 'q',self.GetTimeout()
            #elif 'SecondaryChannel' == property_name:
            #    rv = 's',self.GetSecondaryChannel()
            #elif 'MinInterval' == property_name:
            #    rv = 'u',self.GetMinInterval()
            #elif 'MaxInterval' == property_name:
            #    rv = 'u',self.GetMaxInterval()
            elif 'TxPower' == property_name:
                rv = 'n',self.GetTxPower()
        return rv

    @dbus_objects.dbus_method(interface=bluez_dbus.DBUS_PROPERTIES_INTERFACE,name='Set')
    def SetProperties(self,interface_name: str,property_name: str,value: dbus_objects.types.Variant) -> None:
        log.debug('[Set] property_name = ' + property_name)
        log.debug('[Set] str(type(value))) = ' + str(type(value)) + ', ' + 'str(value) = ' + str(value))
        if bluez_dbus.LE_ADVERTISING_INTERFACE == interface_name:
            if 'Type' == property_name:
                pass
            elif 'Discoverable' == property_name:
                pass
            elif 'DiscoverableTimeout' == property_name:
                pass
            elif 'ServiceUUIDs' == property_name:
                pass
            elif 'SolicitUUIDs' == property_name:
                pass
            elif 'ManufacturerData' == property_name:
                pass
            elif 'ServiceData' == property_name:
                pass
            elif 'Includes' == property_name:
                pass
            elif 'LocalName' == property_name:
                pass
            elif 'Appearance' == property_name:
                pass
            elif 'Timeout' == property_name:
                pass
            elif 'SecondaryChannel' == property_name:
                pass
            elif 'MinInterval' == property_name:
                pass
            elif 'MaxInterval' == property_name:
                pass
            elif 'TxPower' == property_name:
                self.tx_power = value[1]
                print('tx_power = ' + str(self.tx_power))

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_ADVERTISING_INTERFACE,name='Release')
    def Release(self) -> None:
        print('[Release] Hmmmmmmmm')

    @dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    def Type(self) -> str:
        rv = 's',self.get_type()
        log.debug('[Type] type(rv): ' + str(type(rv)) + ', str(rv): ' + str(rv))
        return rv 

    @dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    def Discoverable(self) -> str:
        return self.get_discoverable()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def DiscoverableTimeout(self) -> str:
    #    return self.get_discoverable_timeout()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def ManufacturerData(self) -> []:
    #    return self.get_manufacturer_data()

    @dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    def ServiceUUIDs(self) -> []:
        return self.get_service_uuids()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def SolicitUUIDs(self) -> []:
    #    return self.get_solicit_uuids()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def ServiceData(self) -> {}:
    #    return self.get_service_data()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def Includes(self) -> []:
    #    return self.get_includes()

    @dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    def LocalName(self) -> str:
        return self.get_local_name()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def Appearance(self) -> int:
    #    return self.get_appearance()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def Timeout(self) -> int:
    #    return self.get_timeout()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def SecondaryChannel(self) -> str:
    #    return self.get_secondary_channel()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def MinInterval(self) -> int:
    #    return self.get_min_interval()

    #@dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    #def MaxInterval(self) -> int:
    #    return self.get_max_interval()

    @dbus_objects.dbus_property(interface=bluez_dbus.LE_ADVERTISING_INTERFACE)
    def TxPower(self) -> int:
        return self.get_tx_power()

    def get_type(self):
        return self.type

    def set_type(self,s):
        self.type = s

    def get_service_uuids(self):
        rv = list()
        rv.append(CCS_DATA_SERVICE_UUID)
        return rv

    #def get_solicit_uuids(self):
    #    rv = list()
    #    return rv

    def get_manufacturer_data(self):
        rv = dict()
        rv[0xffff] = b'3230'
        return rv

    #def get_service_data(self):
    #    rv = dict()
    #    return rv

    #def get_data(self):
    #    rv = dict()
    #    return rv

    def get_discoverable(self):
        return self.discoverable

    def get_discoverable_timeout(self):
        return 0

    #def get_includes(self):
    #    rv = list()
    #    return rv

    def get_local_name(self):
        return platform.node()

    #def get_appearance(self):
    #    return 0

    #def get_timeout(self):
    #    return self.timeout

    #def set_timeout(self):
    #    return self.timeout

    #def get_secondary_channel(self):
    #    return "1M"

    #def get_min_interval(self):
    #    return 250

    #def get_max_interval(self):
    #    return 1000

    def get_tx_power(self):
        return self.tx_power 

    def get_all_properties(self,interface_name):
        rv = dict()
        if bluez_dbus.LE_ADVERTISING_INTERFACE == interface_name:
            rv['Type'] = ('s',self.get_type())
            rv['Discoverable'] = ('b',self.get_discoverable())
            #rv['DiscoverableTimeout'] = ('q',self.get_discoverabletimeout())
            rv['ServiceUUIDs'] = ('as',self.get_service_uuids())
            #rv['SolicitUUIDs'] = ('as',self.get_solicit_uuids())
            #rv['ManufacturerData'] = ('a{qay}',self.get_manufacturer_data())
            #rv['ServiceData'] = ('a{qay}',self.get_service_data())
            #rv['Data'] = ('a{qay}',self.get_data())
            #rv['Includes'] = ('as',self.get_includes())
            #rv['LocalName'] = ('s',self.get_local_name())
            #rv['Appearance'] = ('q',self.get_appearance())
            #rv['Timeout'] = ('q',self.get_timeout())
            #rv['SecondaryChannel'] = ('s',self.get_secondary_channel())
            #rv['MinInterval'] = ('u',self.get_min_interval())
            #rv['MaxInterval'] = ('u',self.get_max_interval())
            rv['TxPower'] = ('n',self.get_tx_power())
        return rv

    def get_path(self):
        return self.default_interface_root + '/' + ADVERT_LABEL

    def get_all_interfaces(self):
        rv = dict()
        inner = dict()
        inner[LE_ADVERTISING_INTERFACE] = self.GetAllProperties(GATT_SERVICE_INTERFACE)
        rv[CCS_ADVERT_ROOT] = inner 
        return rv

class Agent(dbus_objects.DBusObject):

    def __init__(self):
        super().__init__(default_interface_root=CCS_AGENT_ROOT)
        self.uuid = CCS_AGENT_UUID

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_AGENT_INTERFACE,name='Release')
    def Release(self) -> None:
        print('[Agent:Release]')

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_AGENT_INTERFACE,name='Cancel')
    def Cancel(self) -> None:
        print('[Agent:Cancel]')

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_AGENT_INTERFACE,name='RequestPinCode')
    def RequestPinCode(self,device: str) -> str:
        print('[Agent:RequestPinCode] ' + str(device))
        return '1234'

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_AGENT_INTERFACE,name='DisplayPinCode')
    def DisplayPinCode(self,device: str,pincode: int) -> None:
        print('[Agent:DisplayPinCode] ' + ', device: ' + str(device) + ', pincode: ' + str(pincode))

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_AGENT_INTERFACE,name='RequestPasskey')
    def RequestPasskey(self,device: str) -> int:
        print('[Agent:RequestPasskey] ' + str(device))
        return 1234

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_AGENT_INTERFACE,name='DisplayPasskey')
    def DisplayPasskey(self,device: str,passkey: int,entered: int) -> None:
        print('[Agent:DisplayPasskey] ' + ', passkey: ' + str(passkey) + ', entered: ' + str(entered))

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_AGENT_INTERFACE,name='RequestConfirmation')
    def RequestConfirmation(self,device: str,passkey: int) -> None:
        print('[Agent:RequestConfirmation] ' + ', device: ' + str(device) + ', passkey: ' + str(passkey))

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_AGENT_INTERFACE,name='RequestAuthorization')
    def RequestAuthorization(self,device: str) -> None:
        print('[Agent:RequestAuthorization] ' + ', device: ' + str(device))

    @dbus_objects.dbus_method(interface=bluez_dbus.LE_AGENT_INTERFACE,name='AuthorizeService')
    def AuthorizeService(self,device: str,uuid: str) -> None:
        print('[Agent:AuthorizeService] ' + ', device: ' + str(device) + ', uuid' + str(uuid))

    

def get_adapter_names_from_xml(xml):
    rv = list()
    root = et.fromstring(xml)
    for child in root:
        if child.tag == 'node':
            if 'name' in child.attrib:
                name = child.attrib['name']
                rv.append(name)
    return rv
        
async def get_adapter_name():
    rv = None
    xml = None
    async with jeepney.io.trio.open_dbus_router(bus='SYSTEM') as rtr:
        try:
            introspectable = jeepney.io.trio.Proxy(Introspectable(bus_name=bluez_dbus.BLUEZ_BUS_NAME,object_path=bluez_dbus.BLUEZ_PATH),rtr)
            xml, = await introspectable.Introspect()
            names = get_adapter_names_from_xml(xml)
            if len(names) > 0:
                if len(names) > 1:
                    log.warn('Multiple interfaces found: ' + str(names))
                rv = names[0]
            else:
                log.error("Couldn't find a bluetooth interface")
        except DBusErrorResponse as e:
            log.error("Couldn't find a bluetooth interface: " + str(e))

    return rv


async def setup_adapter(interface):
    global g_hci

    if None is not interface:
        g_hci = interface
    else:
        g_hci = await get_adapter_name()

    if None is g_hci:
        msg = "Couldn't find a bluetooth adapter"
        raise NoBluetoothAdapter(msg)


    log.info('Using interface: ' + g_hci)

    async with jeepney.io.trio.open_dbus_router(bus='SYSTEM') as rtr:
        try:
            adapter = jeepney.io.trio.Proxy(bluez_dbus.Adapter(g_hci),rtr)
            # Adapter power, returns a nested tuple such as (('b', True),)
            reply = await adapter.GetPowered()
            if 'b' == reply[0][0]:
                if False == reply[0][1]:
                    await adapter.SetPowered(True)
            else:
                s = 'Failed to get power seting for adapter: ' + g_hci
                log.error(s)
                raise RuntimeError(s)
        except DBusErrorResponse as e:
            s = 'Failed to power on adapter(' + g_hci + '): ' + str(e)
            log.error(s)
            raise RuntimeError(s)


async def app():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-i','--interface',help='Bluetooth interface name (i.e. hci0)')
    args = arg_parser.parse_args()

    await setup_adapter(args.interface)

    server = await CcsServer.new(bus='SYSTEM',name=CCS_NAME)

    data_object = CcsData(uuid=CCS_DATA_SERVICE_UUID,is_primary=True)
    # Register the CcsData object with DBUS
    server.register_object(CCS_DATA_ROOT,data_object)

    temp_sensor = Sensor(CCS_AIR_TEMPERATURE_UUID,obj_name=TEMPERATURE_LABEL,server=server)
    data_object.add_sensor(temp_sensor)
    server.register_object(CCS_DATA_ROOT + '/' + TEMPERATURE_LABEL,temp_sensor)

    humidity_sensor = Sensor(CCS_HUMIDITY_UUID,obj_name=HUMIDITY_LABEL,server=server)
    data_object.add_sensor(humidity_sensor)
    server.register_object(CCS_DATA_ROOT + '/' + HUMIDITY_LABEL,humidity_sensor)

    pressure_sensor = Sensor(CCS_AIR_PRESSURE_UUID,obj_name=PRESSURE_LABEL,server=server)
    data_object.add_sensor(pressure_sensor)
    server.register_object(CCS_DATA_ROOT + '/' + PRESSURE_LABEL,pressure_sensor)


    await server.listen()    

if '__main__' == __name__:
    trio.run(app)


