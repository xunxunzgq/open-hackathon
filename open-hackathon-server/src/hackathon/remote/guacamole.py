# -*- coding: utf-8 -*-
#
# -----------------------------------------------------------------------------------
# Copyright (c) Microsoft Open Technologies (Shanghai) Co. Ltd.  All rights reserved.
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# -----------------------------------------------------------------------------------

import sys

sys.path.append("..")
from flask import (
    request,
)
from hackathon.constants import (
    VEStatus,
    VERemoteProvider,
)

from hackathon.database.models import (
    VirtualEnvironment,
)
import json
from hackathon.hackathon_response import forbidden, not_found
from hackathon import Component
from flask import g


class GuacamoleInfo(Component):
    """Process guacamole information"""
    def getConnectInfo(self):
        """
        Get guacamole connection information from DB table virtual_environment according to request arg field of "name"

        :return: value of column remote_paras in DB table virtual_environment
                 if no record is found in DB, return not_found method
                 if record exists but user_id of experiment does not equal global user id, return forbidden method
        :rtype: json form
        """
        connection_name = request.args.get("name")
        guacamole_config = self.db.find_first_object_by(VirtualEnvironment,
                                                        name=connection_name,
                                                        status=VEStatus.RUNNING,
                                                        remote_provider=VERemoteProvider.Guacamole)
        if guacamole_config is None:
            return not_found("not_found")

        if guacamole_config.experiment.user_id != g.user.id:
            return forbidden("forbidden")

        self.log.debug("get guacamole config by id: %s, paras: %s" % (connection_name, guacamole_config.remote_paras))
        return json.loads(guacamole_config.remote_paras)
        # return {
        # "displayname": "ubuntu", "hostname": "139.217.133.53",
        # "name": "174-ubuntu", "password": "acowoman",
        # "port": 10026, "protocol": "ssh", "username": "root"
        # }
