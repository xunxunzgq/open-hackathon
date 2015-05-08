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

__author__ = 'Yifu Huang'

import sys

sys.path.append("..")
from azureUtil import *
from hackathon.log import *
from hackathon.database.models import *


class AzureCloudService:
    """
    Azure cloud service is used as DNS for azure virtual machines
    Note that the public ports of virtual machines on the same cloud service cannot conflict
    Currently the status of cloud service in database is only RUNNING
    """

    def __init__(self, sms, template, template_config):
        self.sms = sms
        self.template = template
        self.template_config = template_config

    def create_cloud_service(self):
        """
        If cloud service not exist, then create it
        Else check whether it created by this function before
        :return:
        """
        user_operation_commit(self.template, CREATE_CLOUD_SERVICE, START)
        cloud_service = self.template_config['cloud_service']
        # avoid duplicate cloud service
        if not self.cloud_service_exists(cloud_service['service_name']):
            # delete old cloud service info in database, cascade delete old deployment, old virtual machine,
            # old vm endpoint and old vm config
            db_adapter.delete_all_objects_by(UserResource, type=CLOUD_SERVICE, name=cloud_service['service_name'])
            db_adapter.commit()
            try:
                self.sms.create_hosted_service(service_name=cloud_service['service_name'],
                                               label=cloud_service['label'],
                                               location=cloud_service['location'])
            except Exception as e:
                user_operation_commit(self.template, CREATE_CLOUD_SERVICE, FAIL, e.message)
                log.error(e)
                return False
            # make sure cloud service is created
            if not self.cloud_service_exists(cloud_service['service_name']):
                m = '%s %s created but not exist' % (CLOUD_SERVICE, ['service_name'])
                user_operation_commit(self.template, CREATE_CLOUD_SERVICE, FAIL, m)
                log.error(m)
                return False
            else:
                user_resource_commit(self.template, CLOUD_SERVICE, cloud_service['service_name'], RUNNING)
                user_operation_commit(self.template, CREATE_CLOUD_SERVICE, END)
        else:
            # check whether cloud service created by this function before
            if db_adapter.count_by(UserResource, type=CLOUD_SERVICE, name=cloud_service['service_name']) == 0:
                m = '%s %s exist but not created by this function before' % \
                    (CLOUD_SERVICE, cloud_service['service_name'])
                user_resource_commit(self.template, CLOUD_SERVICE, cloud_service['service_name'], RUNNING)
            else:
                m = '%s %s exist and created by this function before' % (CLOUD_SERVICE, cloud_service['service_name'])
            user_operation_commit(self.template, CREATE_CLOUD_SERVICE, END, m)
            log.debug(m)
        return True

    def cloud_service_exists(self, name):
        """
        Check whether specific cloud service exist
        :param name:
        :return:
        """
        try:
            props = self.sms.get_hosted_service_properties(name)
        except Exception as e:
            if e.message != 'Not found (Not Found)':
                log.error('%s %s: %s' % (CLOUD_SERVICE, name, e))
            return False
        return props is not None