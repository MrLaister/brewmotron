# -*- coding: utf-8 -*-
import asyncio
import fcntl
import logging
import socket
import struct
import time
from time import strftime

import busio
from adafruit_ht16k33 import segments
from cbpi.api import *
from cbpi.api.config import ConfigType

# 7Seg Required
from smbus import SMBus

# Brewmotron Cache Handler
from brewmotron_cache_handler import get_cache_handler

# from RPLCD.i2c import CharLCD


# import RPi.GPIO as GPIO
# GPIO.setmode(GPIO.BCM)

# pipy related installation of plugin:
# goto folder where CBPI4 is installed (at least the folder which is
# containing the config folder)
# sudo pip3 install cbpi4-7SegDisplay
# sudo cbpi add cbpi4-7SegDisplay

logger = logging.getLogger(__name__)
DEBUG = True  # turn True to show (much) more debug info in app.log

# TODO!! - Bug: 7seg display kills hardware html page when displaying
# information. Needs debugging. Not caused by sensor type - check data
# type handling.
# TODO - Make LED kettle map generic in settings menu; add 3x LEDs for
# boiler association; move to separate plugin
# TODO - Make settings menu lookup functions generic if possible
# TODO - Add push buttons to progress running process; could be separate
# plugin
# TODO - Clean up running code; use states/attributes instead of
# arbitrary data
# TODO (Later) - Make this just a brewmotron plugin with mode switching;
# check I2C contention handling
# TODO (Later) - Add Units (C/F); currently C only

try:
    import RPi.GPIO as GPIO

    GPIO.setmode(GPIO.BCM)
except Exception as e:
    logger.warning(e)


class SSDisplay(CBPiExtension):
    def __init__(self, cbpi):
        self.settinggroupname = "SevenSegmentDisplay_"  # TODO: Change to "BMT-SevenSegmentDisplay_"
        self.cbpi = cbpi
        self.sevsegcounter = 0
        self._task = asyncio.create_task(self.run())

    async def actor_on(self, actor_id):
        gpio_num = await self.get_actor_gpio(actor_id)
        GPIO.output(gpio_num, True)
        return

    async def actor_off(self, actor_id):
        gpio_num = await self.get_actor_gpio(actor_id)

        # print(gpio_num, actor_id)
        GPIO.output(gpio_num, False)
        return

    async def displayall(self, displaystring):
        if self.sevSeg == []:
            return
        else:
            for display in self.sevSeg:
                display.print(displaystring)
        return

    async def initialise_actor(self, actor_id):
        gpio_num = await self.get_actor_gpio(actor_id)
        try:
            GPIO.setup(gpio_num, GPIO.OUT)
            logger.info(str(gpio_num) + "set up as GPIO OUT")
        except Exception as e:
            logger.error(e)
        return

    async def run(self):
        class Display(object):
            def __init__(
                self,
                number,
                hardware,
                mode=None,
                kettle=None,
                sensor=None,
                tempType=None,
            ):
                self.number = number
                self.hardware = hardware
                self.mode = mode
                self.kettle = kettle
                self.sensor = sensor
                self.tempType = tempType

            def print(self, text=""):
                self.hardware.fill(0)
                self.hardware.print(text)

            def printc(self, temp="", fmt="{:3.1f}"):
                self.hardware.fill(0)
                if temp >= 100:
                    temp = "{:3.0f}".format(temp) + "C"
                elif temp > 0:
                    temp = fmt.format(temp) + "C"
                else:
                    temp = "-"
                try:
                    self.hardware.print(temp)
                except Exception as e:
                    print(e)

        logger.info("Seven Segment Display - Info: Starting background task")

        # Initialize cache handler (shared across all brewmotron plugins)
        self.cache = await get_cache_handler(cbpi_instance=self.cbpi)
        logger.info("Seven Segment Display - Cache handler initialized")

        # Globals setup
        refresh = await self.set_display_refresh()
        logger.info("Seven Segment Display - refresh: %s" % refresh)
        SCL = 3
        SDA = 2
        i2c = busio.I2C(SCL, SDA)
        last_target_kettle = None
        enabledActorsList = []
        activeKettleLEDMap = {
            "5gi2srfkySmuvsZWndshEP": "kqyAAU8eaMWKPtWaEc6S9L",
            "JZTezUkmqBUSgPz39hENU9": "5VV8tfWvArVbm93oXhyWAZ",
            "9aSRzC9vXiLhDDiQyjUq3b": "9x34RbRHcq2tuRuYNVrQ9X",
        }  # This needs genericising to the settings menu
        ledIDMap = {
            "kqyAAU8eaMWKPtWaEc6S9L",
            "5VV8tfWvArVbm93oXhyWAZ",
            "9x34RbRHcq2tuRuYNVrQ9X",
        }
        for led in ledIDMap:
            await self.initialise_actor(led)
        # unit = await self.get_cbpi_temp_unit()
        # logger.info('Seven Segment Display - unit: °%s' % unit)

        # per-display setup
        self.sevSeg = []
        displayAddresses = ["0x70", "0x74", "0x72", "0x76", "0x71", "0x75"]

        for i, displayAddress in enumerate(displayAddresses, 1):
            i2caddress = await self.set_displayAddress(
                displayNo=i,
                defaultValue=displayAddress,
                settingSubtitle="Your 7-segment i2c address, looks like "
                + displayAddress
                + ". CBPi reboot required for changes to take effect",
            )

            if DEBUG:
                logger.info("Setup details for: Display_%s" % i)

            display_mode = await self.set_display_mode(i)
            if DEBUG:
                logger.info("Seven Segment Display - display_mode: %s" % display_mode)

            kettle_id = await self.set_kettle(i)
            if DEBUG:
                logger.info("Seven Segment Display - kettle_id: %s" % kettle_id)

            # sensor = await self.set_sensortype_for_sensor_mode(i)
            # if DEBUG: logger.info('Seven Segment Display - sensor: %s' % sensor)

            tempType = await self.set_tempType(i)

            try:
                self.sevSeg.append(
                    Display(
                        i,
                        segments.Seg7x4(i2c, address=i2caddress),
                        display_mode,
                        kettle_id,
                        None,
                        tempType,
                    )
                )
                if DEBUG:
                    logger.info("Seven Segment Display - Info: Display " + str(i + 1) + " object added")
            except Exception as e:
                logger.warning("Seven segment display address setup failed.")
                logger.warning(e)
            pass
        #        for display in self.sevSeg:
        #            display.print("D"+str(i+1))

        if DEBUG:
            logger.info("Seven Segment Display - Info: Display setup complete")

        # ************************************************************
        # ************************************************************
        while True:
            # this is the main code repeated constantly
            refresh_time = await self.set_display_refresh()
            [active_step_name, active_step_temp_target, target_kettle] = await self.get_active_step_values()
            # LEDs can be mapped to active_state['name']; define in settings
            for display in self.sevSeg:
                display.mode = await self.set_display_mode(display.number)
                display.kettle = await self.set_kettle(display.number)
                # display.sensor = await self.set_sensortype_for_sensor_mode(display.number)

                if display.mode == "Kettle":
                    await self.show_kettle(display)
                # elif active_step != 'no active step' and display.mode == 'Sensordisplay':
                #    await self.show_sensor(display)
                else:
                    await self.show_standby(display)
                pass

            if active_step_name == "no active step":
                for led in ledIDMap:
                    await self.actor_off(led)
            else:
                if target_kettle is not None:
                    actor_id = activeKettleLEDMap[target_kettle]
                    if actor_id not in enabledActorsList:
                        enabledActorsList.append(actor_id)
                    for led in ledIDMap:
                        if led == actor_id:
                            await self.actor_on(led)
                        else:
                            await self.actor_off(led)
            await asyncio.sleep(refresh_time)
        pass
        # *********************************************************************************************************

    async def show_standby(self, display):
        display.print("----")
        # ip = await self.set_ip()
        # await asyncio.sleep(1)

    async def show_kettle(self, display):
        display.hardware.print(":")
        if display.kettle is None or display.kettle == "":
            # display.kettle = self.cbpi.config.get('MASH_TUN', None)
            return

        kettlevalues = await self.get_kettle_values(display.kettle)
        kettle_sensor_id = kettlevalues["kettle_sensor_id"]
        sensor_value = self.cbpi.sensor.get_sensor_value(kettle_sensor_id).get("value")
        kettle_target_temp = kettlevalues["kettle_target_temp"]
        try:
            if display.tempType == "Actual":
                display.printc(sensor_value, "{:3.1f}")
            if display.tempType == "Target":
                display.printc(kettle_target_temp, "{:3.0f}")
        except Exception as e:
            logger.warning(e)
            print(e)
        # display_unit = await self.get_cbpi_temp_unit()
        display.hardware.print(";")
        pass

    # async def get_cbpi_version(self):
    #     try:
    #         version = self.cbpi.version
    #     except Exception as e:
    #         logger.warning('no cbpi version found')
    #         logger.warning(e)
    #         version = "no vers."
    #     return version

    # async def get_cbpi_temp_unit(self):
    #     try:
    #         unit = self.cbpi.config.get("TEMP_UNIT", None)
    #     except Exception as e:
    #         logger.warning('no cbpi temp. unit found')
    #         logger.warning(e)
    #         unit = "na"
    #     pass
    #     return unit

    # async def set_ip(self):
    #     if await self.get_ip('wlan0') != 'Not connected':
    #         ip = await self.get_ip('wlan0')
    #     elif await self.get_ip('eth0') != 'Not connected':
    #         ip = await self.get_ip('eth0')
    #     elif await self.get_ip('enxb827eb488a6e') != 'Not connected':
    #         ip = await self.get_ip('enxb827eb488a6e')
    #     else:
    #         ip = 'Not connected'
    #     pass
    #     return ip

    # async def get_ip(self, interface):
    #     ip_addr = 'Not connected'
    #     so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     try:
    #         ip_addr = socket.inet_ntoa(
    #             fcntl.ioctl(
    #                 so.fileno(),
    #                 0x8915,
    #                 struct.pack("256s", bytes(interface.encode())[:15]),
    #             )[20:24])
    #     except Exception as e:
    #         logger.warning('no ip found')
    #         if DEBUG: logger.warning(e)
    #         return ip_addr

    #     return ip_addr

    async def set_displayAddress(self, displayNo, defaultValue, settingSubtitle):
        settingsName = self.settinggroupname + str(displayNo) + "_Address"
        address = self.cbpi.config.get(settingsName, None)
        if address is None:
            try:
                await self.cbpi.config.add(settingsName, defaultValue, ConfigType.STRING, settingSubtitle)
                logger.info(str(settingsName + "added"))
                address = self.cbpi.config.get(settingsName, None)
            except Exception as e:
                logger.warning("Unable to update config for " + settingsName)
                logger.warning(e)

        return int(address, 16)

    async def set_display_refresh(self):
        settingsName = self.settinggroupname + "Refresh"
        ref = self.cbpi.config.get(settingsName, None)
        if ref is None:
            logger.info(settingsName + " added")
            try:
                await self.cbpi.config.add(
                    settingsName,
                    3,
                    ConfigType.SELECT,
                    "Display update time in seconds for all displays. " "CBPi reboot not required",
                    [
                        {"label": "1s", "value": 1},
                        {"label": "2s", "value": 2},
                        {"label": "3s", "value": 3},
                        {"label": "4s", "value": 4},
                        {"label": "5s", "value": 5},
                        {"label": "6s", "value": 6},
                    ],
                )
                ref = self.cbpi.config.get(settingsName, None)
            except Exception as e:
                logger.warning("Unable to update config for: " + settingsName)
                logger.warning(e)

        return ref

    async def set_display_mode(self, displayNo):
        settingsName = self.settinggroupname + str(displayNo) + "_Mode"
        mode = self.cbpi.config.get(settingsName, None)
        if mode is None:
            logger.info(settingsName + " added")
            try:
                await self.cbpi.config.add(
                    settingsName,
                    "Singledisplay",
                    ConfigType.SELECT,
                    "select the mode of Display_" + str(displayNo) + ", consult readme, NO! CBPi reboot " "required",
                    [
                        {"label": "From Kettle", "value": "Kettle"},
                        {"label": "From Sensor", "value": "Sensor"},
                    ],
                )
                mode = self.cbpi.config.get(settingsName, None)
            except Exception as e:
                logger.warning("Unable to update " + settingsName + " config")
                logger.warning(e)
            pass
        pass
        return mode

    async def set_kettle(self, displayNo):
        settingsName = self.settinggroupname + str(displayNo) + "_Kettle"
        kettle_id = self.cbpi.config.get(settingsName, None)
        if kettle_id is None:
            try:
                await self.cbpi.config.add(
                    settingsName,
                    "",
                    ConfigType.KETTLE,
                    "select the kettle to be displayed, consult readme, " "NO! CBPi reboot required",
                )
                logger.info(settingsName + " added")
                kettle_id = self.cbpi.config.get(settingsName, None)
            except Exception as e:
                logger.warning("Unable to update config for " + settingsName)
                logger.warning(e)
            pass
        pass
        return kettle_id

    async def set_tempType(self, displayNo):
        settingsName = self.settinggroupname + str(displayNo) + "_TemperatureType"
        tempType = self.cbpi.config.get(settingsName, None)
        if tempType is None:
            try:
                await self.cbpi.config.add(
                    settingsName,
                    "",
                    ConfigType.SELECT,
                    "select the temperature Type (Actual / Target) to be "
                    "displayed, consult readme, "
                    "NO! CBPi reboot required",
                    [
                        {"label": "---", "value": None},
                        {"label": "Actual", "value": "Actual"},
                        {"label": "Target", "value": "Target"},
                    ],
                )
                logger.info(settingsName + " added")
                tempType = self.cbpi.config.get(settingsName, None)
            except Exception as e:
                logger.warning("Unable to update config for " + settingsName)
                logger.warning(e)
            pass
        pass
        return tempType

    async def get_active_step_values(self):
        noactivestep = ["no active step", "---", None]
        try:
            step_json_obj = await self.cache.get_step_state()
            steps = step_json_obj["steps"]
            last_active_step_target_kettle = None

            result = noactivestep
            for step in steps:
                if step["status"] == "A":
                    try:
                        active_step_name = step["name"]
                    except Exception as e:
                        active_step_name = noactivestep
                        logger.warning(e)
                    pass
                    try:
                        active_step_target_temp = str(step["props"]["Temp"])
                    except Exception as e:
                        active_step_target_temp = "---"
                    pass
                    try:
                        last_active_step_target_kettle = str(step["props"]["Kettle"])
                    except Exception:
                        pass
                    # active_step_timer_value = ("Timer: %s" % (steps[i]["props"]["Timer"])) --> Taken out, but could use later if BMT wants
                    return [
                        active_step_name,
                        active_step_target_temp,
                        last_active_step_target_kettle,
                    ]
                else:
                    result = noactivestep
                pass
            pass
            return result
        except Exception as e:
            logger.warning(e)
            return result
        pass

    async def get_kettle_values(self, kettle_id):
        try:
            kettle_json_obj = await self.cache.get_kettle_state()
            kettles = kettle_json_obj["data"]
            # if DEBUG: logger.info("kettles %s" % kettles)
            i = 0
            result = None
            for kettle in kettles:
                if kettle["id"] == kettle_id:
                    kettle_id = kettle["id"]
                    kettle_name = kettle["name"]
                    kettle_heater_id = kettle["heater"]
                    kettle_sensor_id = kettle["sensor"]
                    kettle_target_temp = kettle["target_temp"]
                    return {
                        "kettle_id": kettle_id,
                        "kettle_name": kettle_name,
                        "kettle_heater_id": kettle_heater_id,
                        "kettle_sensor_id": kettle_sensor_id,
                        "kettle_target_temp": kettle_target_temp,
                    }
                else:
                    result = "no kettle found with id %s" % kettle_id
                pass
                i = i + 1
            pass
            return result
        except Exception as e:
            logger.warning(e)
            return {
                "kettle_id": "error",
                "kettle_name": "error",
                "kettle_heater_id": "error",
                "kettle_sensor_id": "error",
                "kettle_target_temp": 0,
            }
        pass

    pass

    async def get_sensor_values_by_id(self, sensor_id):
        try:
            sensor_json_obj = await self.cache.get_sensor_state()
            sensors = sensor_json_obj["data"]
            if DEBUG:
                logger.info("sensors %s" % sensors)
            i = 0
            while i < len(sensors):
                if sensors[i]["id"] == sensor_id:
                    sensor_type = sensors[i]["type"]
                    sensor_name = sensors[i]["name"]
                    # sensor_id = (sensors[i]['id'])
                    sensor_props = sensors[i]["props"]
                    sensor_value = self.cbpi.sensor.get_sensor_value(sensor_id).get("value")
                    return {
                        "sensor_id": sensor_id,
                        "sensor_name": sensor_name,
                        "sensor_type": sensor_type,
                        "sensor_value": sensor_value,
                        "sensor_props": sensor_props,
                    }
                else:

                    pass
                pass
                i = i + 1
            pass
        except Exception as e:
            logger.info(e)
            return {
                "sensor_id": "error",
                "sensor_name": "error",
                "sensor_type": "error",
                "sensor_value": "error",
                "sensor_props": "error",
            }
        pass
        await asyncio.sleep(1)

    async def get_kettle_gpio(self, actor_id):
        try:
            actor_json_obj = await self.cache.get_actor_state()
            actors = actor_json_obj["data"]

            # if DEBUG: logger.info("kettles %s" % kettles)
            i = 0
            result = None
            for actor in actors:
                if actor["id"] == actor_id:
                    result = actor["props"]["GPIO"]
                    return result
                else:
                    result = "no actor found with id %s" % actor_id
            return result
        except Exception as e:
            logger.warning(e)
            return result

    async def get_actor_gpio(self, actor_id):
        try:
            actor_json_obj = await self.cache.get_actor_state()
            actors = actor_json_obj["data"]
            # if DEBUG: logger.info("kettles %s" % kettles)
            i = 0
            result = None
            for actor in actors:
                if actor["id"] == actor_id:
                    result = actor["props"]["GPIO"]
                    return result
                else:
                    result = "no actor found with id %s" % actor_id
            return result
        except Exception as e:
            logger.warning(e)
            return result


def setup(cbpi):
    cbpi.plugin.register("Seven Segment Display", SSDisplay)
