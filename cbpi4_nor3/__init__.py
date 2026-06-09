# -*- coding: utf-8 -*-
# import os
# from aiohttp import web
import logging

# from unittest.mock import MagicMock, patch
# import asyncio
# import random
# from modules import cbpi
# import cbpi
from cbpi.api import *

# from cbpi.api.base import CBPiBase
# from cbpi.api.http_endpoints import DashBoardHttpEndpoints
# from cbpi.api.config import ConfigType

logger = logging.getLogger(__name__)


@parameters(
    [
        Property.Actor(label="input_actor_a", description="Select an actor as an input."),
        Property.Actor(label="input_actor_b", description="Select an actor as an input."),
        Property.Actor(label="input_actor_c", description="Select an actor as an input."),
    ]
)

# class NOR3(CBPiExtension):
class NOR3(CBPiActor):
    async def on_start(self):
        self.power = 100
        await self.off()
        self.get_state()

    async def on(self, input):
        self.state = True
        await asyncio.sleep(0)

    async def off(self):
        self.state = False
        await asyncio.sleep(0)

    def get_state(self):
        try:
            a_id = self.cbpi.actor.find_by_id(self.id).instance.props["input_actor_a"]
            b_id = self.cbpi.actor.find_by_id(self.id).instance.props["input_actor_b"]
            c_id = self.cbpi.actor.find_by_id(self.id).instance.props["input_actor_c"]

            a = self.cbpi.actor.find_by_id(a_id).instance.state
            b = self.cbpi.actor.find_by_id(b_id).instance.state
            c = self.cbpi.actor.find_by_id(c_id).instance.state

            self.state = not (a or b or c)

        except Exception as e:
            print(e)
        return self.state


def setup(cbpi):
    cbpi.plugin.register("NOR3Actor", NOR3)
    pass
