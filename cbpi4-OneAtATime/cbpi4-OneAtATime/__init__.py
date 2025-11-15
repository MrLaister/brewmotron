# -*- coding: utf-8 -*-
# import os
# from aiohttp import web
# from unittest.mock import MagicMock, patch
import asyncio
import logging

# import random
from cbpi.api import *
from cbpi.api.base import CBPiBase
from cbpi.api.config import ConfigType

logger = logging.getLogger(__name__)


@parameters(
    [
        Property.Actor(
            label="actor", description="Select an actor to be controlled by this group."
        ),
        Property.Select(
            label="OneAtATime group",
            options=[1, 2, 3, 4, 5],
            description="Select a group which this Actor belongs to where only one will be on at a time",
        ),
    ]
)
class OneAtATime(CBPiActor):
    async def on_start(self):
        self.actorPluginType = "OneAtATimeActor"
        self.group = "OneAtATime group"
        self.actors = []
        logger.info("on_start_oneatatime")
        self.power = 100

        logger.info("Loading actors")
        self.loadActorValues("self.actorPluginType")
        logger.info("actors loaded:")
        for actor in self.actors:
            logger.info(actor)
        logger.info("------------")
        await self.off()

    def get_state(self):
        return self.state

    async def run(self):
        await asyncio.sleep(0)

    def init(self, cbpi):
        self.state = False
        self.cbpi = cbpi
        self.cbpi.app.logger.info("OneAtATime plugin initialized.")

        self.actors = []

        return

    async def on(self, input):
        self.loadActorValues(self.actorPluginType)
        try:
            if self.cbpi.actor.find_by_id(self.id).instance.running == True:
                for actor in self.actors:
                    if (actor != self.props["actor"]) and (actor != self.id):
                        logger.info(actor + " is being turned off")
                        print(actor + " is being turned off")
                        await self.cbpi.actor.off(actor)
                logger.info("Actor " + self.props["actor"] + " ON")
                print(
                    "OneAtATime Actor: I am:"
                    + self.id
                    + ", processing Actor:"
                    + self.props["actor"]
                    + " ON"
                )
                self.state = True
                if self.power is None:
                    self.power = 100
                await self.cbpi.actor.on(self.props["actor"], self.power)
            else:
                print("OneAtATime plugin is disabled - please enable to use")
        except Exception as e:
            print(e)
        await asyncio.sleep(0)

    async def off(self):
        logger.info("Actor " + self.props["actor"] + " OFF")
        await self.cbpi.actor.off(self.props["actor"])
        self.state = False

    def get_state(self):
        return self.state

    def loadActorValues(self, actorPluginType):
        try:
            actor_json_obj = self.cbpi.actor.get_state()
            actors = actor_json_obj["data"]
            logger.info("Started looking for saved OneAtATime actors")
            self.actors = []
            for actor in actors:
                if (
                    actor["type"] == actorPluginType
                    and actor["props"][self.group] == self.props[self.group]
                ):
                    logger.info(
                        "appending actor list with "
                        + actor["props"]["actor"]
                        + " with controller ID "
                        + actor["id"]
                    )
                    self.actors.append(actor["id"])
                    self.actors.append(actor["props"]["actor"])
        except Exception as e:
            logger.error(e)

        return


def setup(cbpi):
    cbpi.plugin.register("OneAtATimeActor", OneAtATime)
    pass
