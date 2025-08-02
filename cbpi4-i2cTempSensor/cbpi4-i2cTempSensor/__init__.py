# -*- coding: utf-8 -*-
import os

# from aiohttp import web
import logging

# from unittest.mock import MagicMock, patch
import asyncio
import RPi.GPIO as GPIO
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import math

# import random
from cbpi.api import *

# from cbpi.api.base import CBPiBase
# from cbpi.api.config import ConfigType
from cbpi.api import parameters, CBPiSensor
from cbpi.api.dataclasses import DataType

# TODO make the i2c gather the data. Get the right formula to turn it into temperature, and create a function to do the conversion
# TODO integrate bit that does slow and fast sample rate
# TODO Fix/Debug I2C calls & statup crashes

# SCL = 3
# SDA = 2
# i2c = busio.I2C(SCL, SDA)
# ads = ADS.ADS1115(i2c)
GPIO.setmode(GPIO.BCM)


logger = logging.getLogger(__name__)


class tempProbe:
    def __init__(self, ads, channel, tempProbeName):
        self.ads = ads
        self.channel = channel
        self.tempProbeName = tempProbeName

    def read(self):
        self.lastreading = AnalogIn(self.ads, self.channel)
        self.lastvoltage = self.lastreading.voltage
        self.lastvalue = self.lastreading.value
        # self.lastTemp = TODO FUNCTION below here
        # print(self.tempProbeName, self.lastvoltage)
        return self.lastvoltage  # will return self.lastTemp


@parameters(
    [  # Property.Text(label="i2c address", configurable=True, description="Enter the i2c address of your Temp Sensor"),
        Property.Select(
            label="Channel",
            options=[0, 1, 2, 3],
            description="Choose the channel of your Temp Sensor (0-3)",
        ),
        Property.Text(
            label="Resistor Value",
            configurable=True,
            description="Enter the resistor network value",
        ),
        Property.Text(
            label="Thermistor Nominal Resistance",
            configurable=True,
            description="Enter the thermistor nominal resistance e.g. 10000",
        ),
        Property.Text(
            label="Thermistor Nominal Resistance Temperature",
            configurable=True,
            description="Enter the thermistor nominal resistance temperature e.g. 25",
        ),
        Property.Text(
            label="Thermistor Beta",
            configurable=True,
            description="Enter the thermistor beta (Typically 25/85) value e.g. 3435",
        ),
        Property.Text(
            label="Sample Interval Time - Fast",
            configurable=True,
            description="Enter the fast sample interval time e.g. 1",
        ),
        Property.Text(
            label="Sample Interval Time - Slow",
            configurable=True,
            description="Enter the slow sample interval time e.g. 30",
        ),
        Property.Text(
            label="VMax", configurable=True, description="Enter max voltage (e.g. 3.3)"
        ),
        Property.Kettle(
            label="Kettle",
            description="Select the kettle associatated to use faster interval",
        ),
        Property.Fermenter(
            label="Fermenter",
            description="Select the fermenter associatated to use faster interval",
        ),
    ]
)
# @parameters([])


class i2cTempSensor(CBPiSensor):

    def __init__(self, cbpi, id, props):
        super(i2cTempSensor, self).__init__(cbpi, id, props)
        self.value = 0
        self.lastTemp = float("{:3.1f}".format(0))
        # self.i2caddress = self.props.get("i2c address")
        self.channel = self.props.get("Channel")
        self.resistorvalue = float(self.props.get("Resistor Value"))
        self.thermistorR = float(self.props.get("Thermistor Nominal Resistance"))
        self.thermistorRT = float(
            self.props.get("Thermistor Nominal Resistance Temperature")
        )
        self.beta = float(self.props.get("Thermistor Beta"))
        self.fastUpdate = float(self.props.get("Sample Interval Time - Fast"))
        self.slowUpdate = float(self.props.get("Sample Interval Time - Slow"))
        self.kettle = self.props.get("Kettle")
        self.fermenter = self.props.get("Fermenter")
        self.vmax = float(self.props.get("VMax"))
        SCL = 3
        SDA = 2
        i2c = busio.I2C(SCL, SDA)
        self.ads = ADS.ADS1115(i2c)

    async def run(self):
        print("Sensor Run")
        print(self.running)
        while True:
            try:
                self.lastTemp = await self.readadc()
            except Exception as e:
                logger.warning(e)
                print(e)
            self.log_data(self.lastTemp)
            self.push_update(self.lastTemp)
            await asyncio.sleep(1)

    def get_state(self):
        return dict(value=self.lastTemp)

    def get_value(self):
        return self.lastTemp

    async def readadc(self):
        if self.channelSelect(self.channel) is None:
            return 0
        self.lastreading = AnalogIn(self.ads, self.channelSelect(self.channel))
        self.lastvoltage = float(self.lastreading.voltage)
        return self.tempConversion()

    def channelSelect(self, channel):
        if channel == 0:
            return ADS.P0
        if channel == 1:
            return ADS.P1
        if channel == 2:
            return ADS.P2
        if channel == 3:
            return ADS.P3
        return None

    def tempConversion(self):
        # Network assumes resistor to Vmax, with NTC probe to gnd
        if self.lastvoltage > self.vmax:
            self.lastvoltage = self.vmax - 0.00001
        logger.info("VMAX: " + str(self.vmax))
        logger.info("Vmeas: " + str(self.lastvoltage))
        a1 = self.lastvoltage / self.vmax
        rTherm = (self.resistorvalue * a1) / (1 - a1)

        # print("MATH INPUTS:")
        # print(str(self.vmax))
        # print(str(self.lastvoltage))
        # print(str(a1))
        # print(str(rTherm))
        # print(str(self.thermistorR))
        # print(str(self.beta))

        steinhart = math.log(rTherm / self.thermistorR) / self.beta  # log(R/Ro) / beta
        steinhart += 1.0 / (self.thermistorRT + 273.15)  # log(R/Ro) / beta + 1/To
        steinhart = (1.0 / steinhart) - 273.15  # Invert, convert to C
        logger.info("RTherm: " + str(rTherm))
        logger.info("Steinhart: " + str(steinhart))
        return float("{:3.1f}".format(steinhart))


def setup(cbpi):
    cbpi.plugin.register("i2cTempSensor", i2cTempSensor)
    pass
