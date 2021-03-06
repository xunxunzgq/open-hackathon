# -*- coding: utf-8 -*-
"""
Copyright (c) Microsoft Open Technologies (Shanghai) Co. Ltd.  All rights reserved.
 
The MIT License (MIT)
 
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
 
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
 
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from hackathon.database.models import *
from hackathon.constants import HACKATHON_BASIC_INFO, VE_PROVIDER
from datetime import timedelta
from hackathon.util import get_now
import json
import os
from os.path import realpath, dirname

# test hackathon
hackathon = db_adapter.find_first_object_by(Hackathon, name="open-xml-sdk")
if hackathon is None:
    hackathon = Hackathon(name="open-xml-sdk", display_name="open hackathon", description="description",
                          event_start_time=get_now(), event_end_time=get_now() + timedelta(days=365),
                          registration_start_time=get_now(),
                          registration_end_time=get_now() + timedelta(days=365),
                          judge_start_time=get_now(), judge_end_time=get_now() + timedelta(days=365),
                          basic_info=json.dumps({
                              HACKATHON_BASIC_INFO.AUTO_APPROVE: False,
                              HACKATHON_BASIC_INFO.RECYCLE_ENABLED: False,
                              HACKATHON_BASIC_INFO.ORGANIZERS: [],
                              HACKATHON_BASIC_INFO.BANNERS: "",
                              HACKATHON_BASIC_INFO.LOCATION: "",
                              HACKATHON_BASIC_INFO.MAX_ENROLLMENT: 0,
                              HACKATHON_BASIC_INFO.PRE_ALLOCATE_ENABLED: False,
                              HACKATHON_BASIC_INFO.PRE_ALLOCATE_NUMBER: 1,
                          }),
                          status=1)
    db_adapter.add_object(hackathon)

# test docker host server
docker_host = DockerHostServer(vm_name="osslab-vm-19", public_dns="osslab-vm-19.chinacloudapp.cn",
                               public_ip="42.159.97.143", public_docker_api_port=4243, private_ip="10.209.14.33",
                               private_docker_api_port=4243, container_count=0, container_max_count=100,
                               hackathon=hackathon)
if db_adapter.find_first_object_by(DockerHostServer, vm_name=docker_host.vm_name, hackathon_id=hackathon.id) is None:
    db_adapter.add_object(docker_host)

# test template: ubuntu terminal
template_dir = dirname(realpath(__file__)) + '/hackathon/resources'
template_url = template_dir + os.path.sep + "kaiyuanshe-ut.js"

template = Template(name="sample-template-for-docker",
                    url=template_url,
                    provider=VE_PROVIDER.DOCKER,
                    status=1,
                    virtual_environment_count=1,
                    description="")
if db_adapter.find_first_object_by(Template, name=template.name) is None:
    db_adapter.add_object(template)

hackathon_template_rel = HackathonTemplateRel(hackathon_id=hackathon.id,
                                              template_id=template.id,
                                              update_time=get_now())
if db_adapter.find_first_object_by(HackathonTemplateRel, template_id=template.id, hackathon_id=hackathon.id) is None:
    db_adapter.add_object(hackathon_template_rel)
