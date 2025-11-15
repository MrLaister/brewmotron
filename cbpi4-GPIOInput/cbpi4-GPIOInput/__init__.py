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
        Property.Select(
            label="Inverted",
            options=["Yes", "No"],
            description="No: Active on high; Yes: Active on low",
        ),
        Property.Actor(
            label="LinkedActor",
            description="Associated Actor which mirrors the Actor Input",
        ),
    ]
)
class GPIOInput(CBPiActor):
    # Custom property which can be configured by the user
    # @action("Set Power", parameters=[Property.Number(label="Power", configurable=True,description="Power Setting [0-100]")])
    # async def setpower(self,Power = 100 ,**kwargs):
    #     self.power=int(Power)
    #     if self.power < 0:
    #         self.power = 0
    #     if self.power > 100:
    #         self.power = 100
    #     await self.set_power(self.power)
    def init(self, cbpi):
        self.state = False
        self.cbpi = cbpi
        self.cbpi.app.logger.info("GPIOInput plugin initialized.")

    async def on_start(self):
        self.power = 100
        await self.off()
        self.get_state()
        await asyncio.sleep(0)

    def get_state(self):
        gpio = self.props.get("GPIO")
        GPIO.setup(gpio, GPIO.IN)
        newInput = GPIO.input(gpio)
        if self.props.get("Inverted") == "No":
            high = 1
            low = 0
        elif self.props.get("Inverted") == "Yes":
            high = 0
            low = 1
        # if newInput == high: asyncio.create_task(self.on())
        # elif newInput == low: asyncio.create_task(self.off())
        if (newInput == high) and (self.state == False):
            print(
                "GPIOInput: event change detected - Off to On - Inverted: "
                + self.props.get("Inverted")
            )
            self.state = True
            asyncio.create_task(self.on())
        if (newInput == low) and (self.state == True):
            print(
                "GPIOInput: event change detected - On to Off - Inverted: "
                + self.props.get("Inverted")
            )
            self.state = False
            asyncio.create_task(self.off())
        # print(["input GPIO", gpio, "Output Actor",
        # self.props.get("LinkedActor"), self.id, "State:", self.state,
        # self.props.get("Inverted")])
        return self.state

    async def on(self, power=None):
        linkedActorID = self.props.get("LinkedActor", None)
        if linkedActorID is not None:
            print("GPIOInput: As " + self.id + ", Turning on: " + linkedActorID)
            await self.cbpi.actor.on(linkedActorID, 100)
            await self.cbpi.actor.actor_update(linkedActorID, 100)
        self.state = True
        await asyncio.sleep(0)

    async def off(self):
        linkedActorID = self.props.get("LinkedActor", None)
        if linkedActorID is not None:
            print("GPIOInput: As " + self.id + ", Turning off: " + linkedActorID)
            await self.cbpi.actor.off(linkedActorID)
            await self.cbpi.actor.actor_update(linkedActorID, 100)
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

    cbpi.plugin.register("GPIOInput", GPIOInput)
