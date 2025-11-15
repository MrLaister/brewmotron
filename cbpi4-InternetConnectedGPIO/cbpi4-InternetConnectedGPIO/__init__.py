import asyncio
import logging
import os
from unittest.mock import MagicMock, patch

from cbpi.api import *

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
except Exception:
    logger.warning("Failed to load RPi.GPIO. Using Mock instead")
    MockRPi = MagicMock()
    modules = {"RPi": MockRPi, "RPi.GPIO": MockRPi.GPIO}
    patcher = patch.dict("sys.modules", modules)
    patcher.start()
    import RPi.GPIO as GPIO

mode = GPIO.getmode()
if mode is None:
    GPIO.setmode(GPIO.BCM)


@parameters(
    [
        Property.Select(
            label="GPIO",
            options=[
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
            ],
        ),
        Property.Select(label="SleepTime_Connected", options=[1, 5, 10, 30, 60, 300, 600]),
        Property.Select(label="SleepTime_Disconnected", options=[1, 5, 10, 30, 60]),
    ]
)
class GPIOInternetConnected(CBPiActor):
    def init(self, cbpi):
        self.state = False
        self.cbpi = cbpi
        self.cbpi.app.logger.info("GPIOInternetConnected plugin initialized.")

    async def on_start(self):
        self.power = 100
        gpio = self.props.get("GPIO")
        GPIO.setup(gpio, GPIO.OUT)
        await self.off()
        await asyncio.sleep(0)
        asyncio.create_task(self.pingloop())

    async def pingloop(self):
        while True:
            previous_state = self.state
            state = self.check_connected()
            if state != previous_state:
                if state:
                    self.state = True
                    try:
                        asyncio.create_task(self.on())
                    except Exception:
                        pass
                else:
                    self.state = False
                    try:
                        asyncio.create_task(self.off())
                    except Exception:
                        pass
            if self.state == True:
                refreshtime = self.props.get("SleepTime_Connected", 30)
            else:
                refreshtime = self.props.get("SleepTime_Disconnected", 1)
            await asyncio.sleep(refreshtime)

    def check_connected(self):
        hostname = "google.com"
        response = os.system("ping -c 1 " + hostname)
        if response == 0:
            return True
        else:
            return False

    def get_state(self):
        return self.state

    async def on(self, power=None):
        gpio = self.props.get("GPIO", None)
        if gpio is not None:
            GPIO.output(gpio, True)
        self.state = True
        await asyncio.sleep(0)

    async def off(
        self,
    ):
        gpio = self.props.get("GPIO", None)
        if gpio is not None:
            GPIO.output(gpio, False)
        self.state = False
        await asyncio.sleep(0)

    async def set_power(self, power=100):
        self.power = power
        await self.cbpi.actor.actor_update(self.id, power)


def setup(cbpi):
    """
    This method is called by the server during startup
    Here you need to register your plugins at the server

    :param cbpi: the cbpi core
    :return:
    """

    cbpi.plugin.register("InternetConnected GPIO", GPIOInternetConnected)
