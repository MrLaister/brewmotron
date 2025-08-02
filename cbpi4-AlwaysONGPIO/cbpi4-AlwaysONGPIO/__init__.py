import asyncio
import logging
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
if mode == None:
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
        )
    ]
)
class GPIOAON(CBPiActor):
    def init(self, cbpi):
        self.state = True
        self.cbpi = cbpi
        self.cbpi.app.logger.info("GPIOAON plugin initialized.")

    async def on_start(self):
        self.power = 100
        gpio = self.props.get("GPIO")
        GPIO.setup(gpio, GPIO.OUT)
        await self.on()
        await asyncio.sleep(0)

    def get_state(self):
        try:
            asyncio.create_task(self.on())
        except:
            pass
        return True

    async def on(self, power=None):
        gpio = self.props.get("GPIO", None)
        if gpio is not None:
            GPIO.output(gpio, True)
        self.state = True
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

    cbpi.plugin.register("AlwaysON GPIO", GPIOAON)
