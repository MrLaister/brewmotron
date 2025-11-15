# -*- coding: utf-8 -*-
# import os
# from aiohttp import web
# from unittest.mock import MagicMock, patch
import asyncio
import logging

# import random
from cbpi.api import *
from cbpi.api.actor import CBPiActor
from cbpi.api.config import ConfigType

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO

    GPIO.setmode(GPIO.BCM)
except Exception as e:
    logger.warning(e)


@parameters(
    [
        Property.Actor(label="OFF_State", description="Select a GPIO Actor showing OFF Mode"),
        Property.Actor(label="Clean_State", description="Select a GPIO Actor showing Clean Mode"),
        Property.Actor(label="Brew_State", description="Select a GPIO Actor showing Brew Mode"),
        Property.Actor(
            label="Ferment_State",
            description="Select a GPIO Actor showing Ferment Mode",
        ),
    ]
)

# @cbpi.backgroundtask(key="key_task", interval=1)
# def key_OFF_task():


#    pass
# TODO - Key states: (1) detect if OFF and output as an actor (2) Loads
# cleaning recipe (3) Unloads cleaning recipe (4) Disables high power outputs
class BMTKey(CBPiExtension):
    def __init__(self, cbpi):
        self.actors = []
        self.settinggroupname = "BMT-Key_"
        self.settingDescription = "Select an Actor to indicate when this mode is active (high)"
        self.cbpi = cbpi
        self.keyStates = [
            ("Off", "OFF_State", ""),
            ("Clean", "Clean_State", ""),
            ("Brew", "Brew_State", ""),
            ("Ferment", "Ferment_State", ""),
        ]
        self.mode = self.keyStates[0][0]
        self.enableMode(self.mode)
        try:
            self._task = asyncio.create_task(self.run())
        except Exception as e:
            print(e)

    async def run(self):
        while True:
            await self.check_state()
            await asyncio.sleep(1)

    async def disableHPActors(self):
        print("Disabling OneAtATime Actors")
        self.loadActorValues("OneAtATimeActor")
        for actor in self.actors:
            await self.cbpi.actor.off(actor)
            if self.cbpi.actor.find_by_id(actor).instance.running == True:
                await self.cbpi.actor.stop(actor)

    async def enableHPActors(self):
        print("Enabling OneAtATime Actors")
        self.loadActorValues("OneAtATimeActor")
        for actor in self.actors:
            if self.cbpi.actor.find_by_id(actor).instance.running == False:
                await self.cbpi.actor.start(actor)

    def enableMode(self, modeName):
        print(["Enabling", modeName, "mode"])

        if modeName == self.keyStates[0][0]:
            asyncio.create_task(self.disableHPActors())
            # TODO: Turn off 7Seg Screens & selected LEDs
            # TODO: Enable use of recipes, load screen 1
        elif modeName == self.keyStates[1][0]:
            asyncio.create_task(self.enableHPActors())
            # TODO: Turn on 7Seg Screens & selected LEDs
            # TODO: Enable use of cleaning recipe, load screen 2
        elif modeName == self.keyStates[2][0]:
            asyncio.create_task(self.enableHPActors())
            # TODO: Turn on 7Seg Screens & selected LEDs
            # TODO: Enable use of recipes, load screen 3
        elif modeName == self.keyStates[3][0]:
            asyncio.create_task(self.disableHPActors())
            # TODO: Turn off 7Seg Screens & selected LEDs
            # TODO: OPTIONAL - enable fermentation temperature and duration to
            # be displayed on the 7seg displays alongside a toggle button press
            # TODO: Enable use of recipes, load screen 4

        return

    async def check_state(self):
        logger.info("BMT-Key: Checking keystate")
        newModeList = []
        truecount = 0

        for modeName, modeID, actorID in self.keyStates:
            actorID = await self.get_mode_actorID(modeName, self.settingDescription)
            modeState = self.cbpi.actor.find_by_id(actorID).instance.state
            await self.cbpi.actor.actor_update(actorID, 100)
            if modeState == True:
                truecount += 1
                newModeList.append(modeName)

        if truecount == 0:
            print("WARNING - No key states detected")
        elif truecount == 1:
            self.newMode = newModeList[0]
            if self.mode != self.newMode:
                self.mode = self.newMode
                self.enableMode(self.mode)
        elif truecount > 1:
            print("WARNING - Multiple key states detected")

        return

    async def get_mode_actorID(self, stateName, settingDescription):
        settingsName = self.settinggroupname + stateName + "_GPIO"
        mode_actorID = self.cbpi.config.get(settingsName, None)
        if mode_actorID is None:
            try:
                await self.cbpi.config.add(settingsName, "", ConfigType.ACTOR, settingDescription)
                logger.info(str(settingsName + "added"))
                mode_actorID = self.cbpi.config.get(settingsName, None)
            except Exception as e:
                logger.warning("Unable to update config for " + settingsName)
                logger.warning(e)
        return mode_actorID

    def loadActorValues(self, actorPluginType):
        try:
            actor_json_obj = self.cbpi.actor.get_state()
            actors = actor_json_obj["data"]
            logger.info("Started looking for saved OneAtATime actors")
            self.actors = []
            for actor in actors:
                if actor["type"] == actorPluginType:
                    logger.info("appending actor list with " + actor["props"]["actor"] + " with controller ID " + actor["id"])
                    self.actors.append(actor["id"])
                    self.actors.append(actor["props"]["actor"])
        except Exception as e:
            logger.error(e)

        return


def setup(cbpi):
    cbpi.plugin.register("BMT-Key", BMTKey)
