import asyncio
import logging
from unittest.mock import MagicMock, patch

from cbpi.api import *

# from cbpi.controller.kettle_controller import KettleController
# from cbpi.controller.step_controller import StepController
from cbpi.api.step import StepMove, StepResult, StepState

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
        Property.Select(
            label="Button Function",
            options=["+10", "+1", "Select", "-1", "-10"],
            description="Map button to Brewmotron Function",
        ),
    ]
)
class BMT_MomentaryButton(CBPiActor):
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

        if (newInput == high) and (self.state == False):
            print("BMT_MomentaryButtons: event change detected - Off to On - Inverted: " + self.props.get("Inverted"))
            self.state = True
            asyncio.create_task(self.on())
        if (newInput == low) and (self.state == True):
            print("BMT_MomentaryButtons: event change detected - On to Off - Inverted: " + self.props.get("Inverted"))
            self.state = False
            asyncio.create_task(self.off())
        # print(["input GPIO", gpio, "Output Actor",
        # self.props.get("LinkedActor"), self.id, "State:", self.state,
        # self.props.get("Inverted")])
        return self.state

    async def on(self, power=None):
        self.state = True
        if self.props.get("Button Function") == "Select":
            await self.progress()
        elif self.props.get("Button Function") == "+10":
            await self.temp_change(10)
        elif self.props.get("Button Function") == "+1":
            await self.temp_change(1)
        elif self.props.get("Button Function") == "-1":
            await self.temp_change(-1)
        elif self.props.get("Button Function") == "-10":
            await self.temp_change(-10)

        await asyncio.sleep(0)

    async def off(self):
        self.state = False
        await asyncio.sleep(0)

    async def set_power(self, power=100):
        self.power = power
        await self.cbpi.actor.actor_update(self.id, power)

    async def temp_change(self, tempIncrement):
        [targetTemp, kettle_id] = self.get_active_step_values()
        if targetTemp and kettle_id:
            targetTemp = self.cbpi.kettle.find_by_id(kettle_id).target_temp
            print(["Current", self.cbpi.kettle.find_by_id(kettle_id).target_temp])
            newTargetTemp = int(targetTemp) + tempIncrement
            if newTargetTemp > 100:
                newTargetTemp = 100
            elif newTargetTemp < 0:
                newTargetTemp = 0
            await self.cbpi.kettle.set_target_temp(kettle_id, newTargetTemp)
            print(["Updated", self.cbpi.kettle.find_by_id(kettle_id).target_temp])
        else:
            print("No active step/kettle")
            await asyncio.sleep(0)

    async def progress(self):
        step = self.cbpi.step.find_by_status(StepState.ACTIVE)
        if step:
            try:
                await self.cbpi.step.next()
            except Exception as e:
                logger.warning(e)
        else:
            pass
            # TODO: This is the part where I can do manual control of kettles - this cycles through the kettle selection manually.
            # TODO: OR - I could start the brew off from here from a button press...

    def get_active_step_values(self):
        targetTemp = "---"
        kettle_id = None
        noActiveStep = [targetTemp, kettle_id]
        try:
            step_json_obj = self.cbpi.step.get_state()
            steps = step_json_obj["steps"]

            for step in steps:
                if step["status"] == "A":
                    targetTemp = str(step["props"]["Temp"])
                    kettle_id = str(step["props"]["Kettle"])
                    return [targetTemp, kettle_id]
        except Exception as e:
            logger.warning(e)
        return noActiveStep


def setup(cbpi):
    """
    This method is called by the server during startup
    Here you need to register your plugins at the server

    :param cbpi: the cbpi core
    :return:
    """

    cbpi.plugin.register("BMT-MomentaryButton", BMT_MomentaryButton)
