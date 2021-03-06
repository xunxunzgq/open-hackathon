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
import imghdr

from werkzeug.exceptions import PreconditionFailed, InternalServerError, BadRequest
from flask import g, request

from hackathon.database import Hackathon, User, AdminHackathonRel, DockerHostServer, HackathonLike, \
    HackathonStat, HackathonConfig, HackathonTag, UserHackathonRel, HackathonOrganizer
from hackathon.hackathon_response import internal_server_error, ok, not_found, forbidden
from hackathon.constants import HACKATHON_BASIC_INFO, ADMIN_ROLE_TYPE, HACK_STATUS, RGStatus, HTTP_HEADER, \
    FILE_TYPE, HACK_TYPE, HACKATHON_STAT
from hackathon import RequiredFeature, Component, Context

__all__ = ["HackathonManager"]

util = RequiredFeature("util")


class HackathonManager(Component):
    """Component to manage hackathon

    Note that it only handle operations directly related to Hackathon table. Things like registerd users, templates are
    in separated components
    """

    admin_manager = RequiredFeature("admin_manager")
    user_manager = RequiredFeature("user_manager")
    register_manager = RequiredFeature("register_manager")

    def is_hackathon_name_existed(self, name):
        """Check whether hackathon with specific name exists or not

        :type name: str|unicode
        :param name: name of hackathon

        :rtype: bool
        :return True if hackathon with specific name exists otherwise False
        """
        hackathon = self.get_hackathon_by_name(name)
        return hackathon is not None

    def is_recycle_enabled(self, hackathon):
        key = HACKATHON_BASIC_INFO.RECYCLE_ENABLED
        return self.get_basic_property(hackathon, key, False)

    def get_hackathon_by_name(self, name):
        """Get hackathon accoring the unique name

        :type name: str|unicode
        :param name: name of hackathon

        :rtype: Hackathon
        :return hackathon instance if found else None
        """
        if not name:
            return None

        return self.db.find_first_object_by(Hackathon, name=name)

    def get_hackathon_by_id(self, hackathon_id):
        """Query hackathon by id

        :return hackathon instance or None
        """
        return self.db.find_first_object_by(Hackathon, id=hackathon_id)

    def get_hackathon_detail(self, hackathon):
        user = None
        if self.user_manager.validate_login():
            user = g.user

        return self.__get_hackathon_detail(hackathon, user)

    def get_hackathon_stat(self, hackathon):

        def internal_get_stat():
            return self.__get_hackathon_stat(hackathon)

        cache_key = "hackathon_stat_%s" % hackathon.id
        return self.cache.get_cache(key=cache_key, createfunc=internal_get_stat)

    def get_hackathon_list(self, args):
        # get values from request's QueryString
        page = int(args.get("page", 1))
        per_page = int(args.get("per_page", 20))
        order_by = args.get("order_by", "create_time")
        status = args.get("status")
        name = args.get("name")

        # build query by search conditions and order_by
        query = Hackathon.query
        if status:
            query = query.filter(Hackathon.status == status)
        if name:
            query = query.filter(Hackathon.name.like("%" + name + "%"))

        if order_by == "create_time":
            query = query.order_by(Hackathon.create_time.desc())
        else:
            query = query.order_by(Hackathon.id.desc())

        # perform db query with pagination
        pagination = self.db.paginate(query, page, per_page)

        # check whether it's anonymous user or not
        user = None
        if self.user_manager.validate_login():
            user = g.user

        def func(hackathon):
            return self.__get_hackathon_detail(hackathon, user)

        # return serializable items as well as total count
        return self.util.paginate(pagination, func)

    def get_pre_allocate_enabled_hackathon_list(self):
        # only online hackathons will be in consideration
        online = self.get_online_hackathons()
        pre_list = filter(lambda hackathon: hackathon.is_pre_allocate_enabled(), online)
        return [h.id for h in pre_list]

    def get_online_hackathons(self):
        return self.db.find_all_objects(Hackathon, Hackathon.status == HACK_STATUS.ONLINE)

    def get_user_hackathon_list_with_detail(self, user_id):
        user = self.user_manager.get_user_by_id(user_id)
        user_hack_list = self.db.session().query(Hackathon, UserHackathonRel) \
            .outerjoin(UserHackathonRel, UserHackathonRel.user_id == user_id) \
            .filter(UserHackathonRel.deleted != 1, UserHackathonRel.user_id == user_id).all()

        return map(lambda h: self.__get_hackathon_detail(h, user), user_hack_list)

    def get_recyclable_hackathon_list(self):
        all_hackathon = self.db.find_all_objects(Hackathon)
        return filter(lambda h: self.is_recycle_enabled(h), all_hackathon)

    def get_entitled_hackathon_list_with_detail(self, user):
        hackathon_ids = self.admin_manager.get_entitled_hackathon_ids(user.id)
        if -1 in hackathon_ids:
            hackathon_list = self.db.find_all_objects(Hackathon)
        else:
            hackathon_list = self.db.find_all_objects(Hackathon, Hackathon.id.in_(hackathon_ids))

        return map(lambda h: self.__get_hackathon_detail(h, user), hackathon_list)

    def get_basic_property(self, hackathon, key, default=None):
        """Get basic property of hackathon from HackathonConfig"""
        config = self.db.find_first_object_by(HackathonConfig, key=key, hackathon_id=hackathon.id)
        if config:
            return config.value
        return default

    def get_all_properties(self, hackathon):
        configs = self.db.find_all_objects_by(HackathonConfig, hackathon_id=hackathon.id)
        return [c.dic() for c in configs]

    def set_basic_property(self, hackathon, properties):
        """Set basic property in table HackathonConfig"""
        if isinstance(properties, list):
            map(lambda p: self.__set_basic_property(hackathon, p), properties)
        else:
            self.__set_basic_property(hackathon, properties)

        self.cache.invalidate(self.__get_config_cache_key(hackathon))
        return ok()

    def delete_property(self, hackathon, key):
        self.db.delete_all_objects_by(HackathonConfig, hackathon_id=hackathon.id, key=key)
        return ok()

    def get_recycle_minutes(self, hackathon):
        key = HACKATHON_BASIC_INFO.RECYCLE_MINUTES
        minutes = self.get_basic_property(hackathon, key, 60)
        return int(minutes)

    def validate_hackathon_name(self):
        if HTTP_HEADER.HACKATHON_NAME in request.headers:
            try:
                hackathon_name = request.headers[HTTP_HEADER.HACKATHON_NAME]
                hackathon = self.get_hackathon_by_name(hackathon_name)
                if hackathon is None:
                    self.log.debug("cannot find hackathon by name %s" % hackathon_name)
                    return False
                else:
                    g.hackathon = hackathon
                    return True
            except Exception as ex:
                self.log.error(ex)
                self.log.debug("hackathon_name invalid")
                return False
        else:
            self.log.debug("hackathon_name not found in headers")
            return False

    def create_new_hackathon(self, context):
        """Create new hackathon based on the http body

        Hackathon name is unique so duplicated names are not allowd.

        :type context: Context
        :param context: the body of http request that contains fields to create a new hackathon

        :rtype: dict
        """
        hackathon = self.get_hackathon_by_name(context.name)
        if hackathon is not None:
            raise PreconditionFailed("hackathon name already exists")

        self.log.debug("add a new hackathon:" + repr(context))
        new_hack = self.__create_hackathon(context)

        # todo remove the following line ASAP
        self.__test_data(new_hack)

        return new_hack.dic()

    def update_hackathon(self, args):
        """Update hackathon properties

        :type args: dict
        :param args: arguments from http request body that contains properties with new values

        :rtype dict
        :return hackathon in dict if updated successfully.
        """
        self.log.debug("update a exist hackathon insert args: %r" % args)
        hackathon = g.hackathon

        try:
            update_items = self.__parse_update_items(args, hackathon)
            self.log.debug("update hackathon items :" + str(args))
            self.db.update_object(hackathon, **update_items)
            return hackathon.dic()
        except Exception as e:
            self.log.error(e)
            return internal_server_error("fail to update hackathon")

    def upload_files(self):
        """Handle uploaded files from http request"""
        self.__validate_upload_files()

        images = []
        storage = RequiredFeature("storage")
        for file_name in request.files:
            file_storage = request.files[file_name]
            self.log.debug("upload image file : " + file_name)
            context = Context(
                hackathon_name=g.hackathon.name,
                file_name=file_storage.filename,
                file_type=FILE_TYPE.HACK_IMAGE,
                content=file_storage
            )
            context = storage.save(context)
            image = {
                "name": file_storage.filename,
                "url": context.url,
                "thumbnailUrl": context.url,
                "deleteUrl": '/api/admin/file?key=' + context.file_name
            }
            # context.file_name is a random name created by server, file.filename is the original name
            images.append(image)

        return {"files": images}

    def like_hackathon(self, user, hackathon):
        like = self.db.find_first_object_by(HackathonLike, user_id=user.id, hackathon_id=hackathon.id)
        if not like:
            like = HackathonLike(user_id=user.id, hackathon_id=hackathon.id)
            self.db.add_object(like)
            self.db.commit()

            # increase the count of users that like this hackathon
            self.increase_hackathon_stat(hackathon, HACKATHON_STAT.LIKE, 1)

        return ok()

    def unlike_hackathon(self, user, hackathon):
        self.db.delete_all_objects_by(HackathonLike, user_id=user.id, hackathon_id=hackathon.id)
        self.db.commit()

        # sync the like count
        like_count = self.db.count_by(HackathonLike, hackathon_id=hackathon.id)
        self.update_hackathon_stat(hackathon, HACKATHON_STAT.LIKE, like_count)
        return ok()

    def update_hackathon_stat(self, hackathon, stat_type, count):
        """Increase or descrease the count for certain hackathon stat

        :type hackathon: Hackathon
        :param hackathon: instance of Hackathon to be counted

        :type stat_type: str|unicode
        :param stat_type: type of stat that defined in constants.py#HACKATHON_STAT

        :type count: int
        :param count: the new count for this stat item
        """
        stat = self.db.find_first_object_by(HackathonStat, hackathon_id=hackathon.id, type=stat_type)
        if stat:
            stat.count = count
        else:
            stat = HackathonStat(hackathon_id=hackathon.id, type=stat_type, count=count)

        if stat.count < 0:
            stat.count = 0
        self.db.commit()

    def increase_hackathon_stat(self, hackathon, stat_type, increase):
        """Increase or descrease the count for certain hackathon stat

        :type hackathon: Hackathon
        :param hackathon: instance of Hackathon to be counted

        :type stat_type: str|unicode
        :param stat_type: type of stat that defined in constants.py#HACKATHON_STAT

        :type increase: int
        :param increase: increase of the count. Can be positive or negative
        """
        stat = self.db.find_first_object_by(HackathonStat, hackathon_id=hackathon.id, type=stat_type)
        if stat:
            stat.count += increase
        else:
            stat = HackathonStat(hackathon_id=hackathon.id, type=stat_type, count=increase)
            self.db.add_object(stat)

        if stat.count < 0:
            stat.count = 0
        self.db.commit()

    def get_hackathon_tags(self, hackathon):
        tags = self.db.find_all_objects_by(HackathonTag, hackathon_id=hackathon.id)
        return ",".join([t.tag for t in tags])

    def set_hackathon_tags(self, hackathon, tags):
        """Set hackathon tags

        :type tags: list
        :param tags: a list of str, every str is a tag
        """
        self.db.delete_all_objects_by(HackathonTag, hackathon_id=hackathon.id)
        for tag in tags:
            t = tag.strip('"').strip("'")
            self.db.add_object(HackathonTag(tag=t, hackathon_id=hackathon.id))
        self.db.commit()
        return ok()

    def get_distinct_tags(self):
        """Return all distinct hackathon tags for auto-complete usage"""
        return self.db.session().query(HackathonTag.tag).distinct().all()

    def qet_organizer_by_id(self, organizer_id):
        organizer = self.db.get_object(HackathonOrganizer, organizer_id)
        if organizer:
            return organizer.dic()
        return not_found()

    def create_hackathon_organizer(self, hackathon, body):
        organizer = HackathonOrganizer(hackathon_id=hackathon.id,
                                       name=body["name"],
                                       description=body.get("description"),
                                       homepage=body.get("homepage"),
                                       logo=body.get("logo"),
                                       create_time=self.util.get_now())
        self.db.add_object(organizer)
        return organizer.dic()

    def update_hackathon_organizer(self, hackathon, body):
        organizer = self.db.get_object(HackathonOrganizer, body["id"])
        if not organizer:
            return not_found()
        if organizer.hackathon_id != hackathon.id:
            return forbidden()

        organizer.name = body.get("name", organizer.name)
        organizer.description = body.get("description", organizer.description)
        organizer.homepage = body.get("homepage", organizer.homepage)
        organizer.logo = body.get("logo", organizer.logo)
        organizer.update_time = self.util.get_now()
        self.db.commit()

        return organizer.dic()

    def delete_hackathon_organizer(self, hackathon, organizer_id):
        self.db.delete_all_objects_by(HackathonOrganizer, id=organizer_id, hackathon_id=hackathon.id)
        return ok()

    def __get_hackathon_detail(self, hackathon, user=None):
        """Return hackathon info as well as its details including configs, stat, organizers, like if user logon"""
        detail = hackathon.dic()

        detail["config"] = self.__get_hackathon_configs(hackathon)
        detail["stat"] = self.get_hackathon_stat(hackathon)
        detail["tag"] = self.get_hackathon_tags(hackathon)
        detail["organizer"] = self.__get_hackathon_organizers(hackathon)

        if user:
            detail["user"] = self.user_manager.user_display_info(user)

            like = self.db.find_first_object_by(HackathonLike, user_id=user.id, hackathon_id=hackathon.id)
            if like:
                detail["like"] = like.dic()

            register = self.register_manager.get_registration_by_user_and_hackathon(user.id, hackathon.id)
            if register:
                detail["registration"] = register.dic()

        return detail

    def __create_hackathon(self, context):
        """Insert hackathon and admin_hackathon_rel to database

        We enforce that default config are used during the creation

        :type context: Context
        :param context: context of the args to create a new hackathon

        :rtype: Hackathon
        :return hackathon instance
        """

        new_hack = Hackathon(
            name=context.name,
            display_name=context.display_name,
            ribbon=context.get("ribbon"),
            description=context.get("description"),
            short_description=context.get("short_description"),
            banners=context.get("banners"),
            status=HACK_STATUS.INIT,
            creator_id=g.user.id,
            event_start_time=context.get("event_start_time"),
            event_end_time=context.get("event_end_time"),
            registration_start_time=context.get("registration_start_time"),
            registration_end_time=context.get("registration_end_time"),
            judge_start_time=context.get("judge_start_time"),
            judge_end_time=context.get("judge_end_time"),
            type=context.get("type", HACK_TYPE.HACKATHON)
        )

        # insert into table hackathon
        self.db.add_object(new_hack)

        # add the current login user as admin and creator
        try:
            ahl = AdminHackathonRel(user_id=g.user.id,
                                    role_type=ADMIN_ROLE_TYPE.ADMIN,
                                    hackathon_id=new_hack.id,
                                    status=HACK_STATUS.INIT,
                                    remarks='creator',
                                    create_time=self.util.get_now())
            self.db.add_object(ahl)
        except Exception as ex:
            # TODO: send out a email to remind administrator to deal with this problems
            self.log.error(ex)
            raise InternalServerError("fail to create the default administrator")

        return new_hack

    def __get_hackathon_configs(self, hackathon):

        def __internal_get_config():
            configs = {}
            for c in hackathon.configs.all():
                configs[c.key] = c.value
            return configs

        cache_key = self.__get_config_cache_key(hackathon)
        return self.cache.get_cache(key=cache_key, createfunc=__internal_get_config)

    def __get_hackathon_organizers(self, hackathon):
        organizers = self.db.find_all_objects_by(HackathonOrganizer, hackathon_id=hackathon.id)
        return [o.dic() for o in organizers]

    def __parse_update_items(self, args, hackathon):
        """Parse properties that need to update

        Only those whose value changed items will be returned. Also some static property like id, create_time should
        NOT be updated.

        :type args: dict
        :param args: arguments from http body which contains new values

        :type hackathon: Hackathon
        :param hackathon: the existing Hackathon object which contains old values

        :rtype: dict
        :return a dict that contains all properties that are updated.
        """
        result = {}

        for key in dict(args):
            if dict(args)[key] != hackathon.dic()[key]:
                result[key] = dict(args)[key]

        result.pop('id', None)
        result.pop('create_time', None)
        result.pop('creator_id', None)
        result['update_time'] = self.util.get_now()
        return result

    def __get_hackathon_stat(self, hackathon):
        stats = self.db.find_all_objects_by(HackathonStat, hackathon_id=hackathon.id)
        result = {
            "hackathon_id": hackathon.id,
            "online": 0,
            "offline": 0
        }
        for item in stats:
            result[item.type] = item.count

        reg_list = hackathon.registers.filter(UserHackathonRel.deleted != 1,
                                              UserHackathonRel.status.in_([RGStatus.AUTO_PASSED,
                                                                           RGStatus.AUDIT_PASSED])).all()

        reg_count = len(reg_list)
        if reg_count > 0:
            user_id_list = [r.user_id for r in reg_list]
            user_id_online = self.db.count(User, (User.id.in_(user_id_list) & (User.online == 1)))
            result["online"] = user_id_online
            result["offline"] = reg_count - user_id_online

        return result

    def __get_config_cache_key(self, hackathon):
        return "hackathon_config_%s" % hackathon.id

    def __test_data(self, hackathon):
        """
        create test data for new hackathon. Remove this function after template and docker host feature done
        :param hackathon:
        :return:
        """
        try:
            # test docker host server
            docker_host = DockerHostServer(vm_name="OSSLAB-VM-19", public_dns="osslab-vm-19.chinacloudapp.cn",
                                           public_ip="42.159.97.143", public_docker_api_port=4243,
                                           private_ip="10.209.14.33",
                                           private_docker_api_port=4243, container_count=0, container_max_count=100,
                                           hackathon=hackathon)
            if self.db.find_first_object_by(DockerHostServer, vm_name=docker_host.vm_name,
                                            hackathon_id=hackathon.id) is None:
                self.db.add_object(docker_host)
        except Exception as e:
            self.log.error(e)
            self.log.warn("fail to create test data")

        return

    def __validate_upload_files(self):
        # check file size
        if request.content_length > len(request.files) * self.util.get_config("storage.size_limit_kilo_bytes") * 1024:
            raise BadRequest("more than the file size limited")

        # check each file type
        for file_name in request.files:
            if request.files.get(file_name).filename.endswith('jpg'):
                continue  # jpg is not considered in imghdr
            if imghdr.what(request.files.get(file_name)) is None:
                raise BadRequest("only images can be uploaded")

    def __set_basic_property(self, hackathon, prop):
        """Set basic property in table HackathonConfig"""
        config = self.db.find_first_object_by(HackathonConfig, hackathon_id=hackathon.id, key=prop.key)
        if config:
            config.value = prop.value
        else:
            config = HackathonConfig(key=prop.key,
                                     value=prop.value,
                                     hackathon_id=hackathon.id)
            self.db.add_object(config)
        self.db.commit()


'''
Attach extension methods to Hackathon entity so that we can code like 'if hackathon.is_auto_approve(): ....' where
hackathon is entity of Hackathon that defines in database/models.py.
'''


def is_auto_approve(hackathon):
    hack_manager = RequiredFeature("hackathon_manager")
    value = hack_manager.get_basic_property(hackathon, HACKATHON_BASIC_INFO.AUTO_APPROVE, "1")
    return util.str2bool(value)


def is_pre_allocate_enabled(hackathon):
    hack_manager = RequiredFeature("hackathon_manager")
    value = hack_manager.get_basic_property(hackathon, HACKATHON_BASIC_INFO.PRE_ALLOCATE_ENABLED, "1")
    return util.str2bool(value)


def get_pre_allocate_number(hackathon):
    hack_manager = RequiredFeature("hackathon_manager")
    value = hack_manager.get_basic_property(hackathon, HACKATHON_BASIC_INFO.PRE_ALLOCATE_NUMBER, 1)
    return int(value)


def is_alauda_enabled(hackathon):
    hack_manager = RequiredFeature("hackathon_manager")
    return hack_manager.get_basic_property(hackathon, HACKATHON_BASIC_INFO.ALAUDA_ENABLED, False)


def get_basic_property(hackathon, property_name, default_value=None):
    hack_manager = RequiredFeature("hackathon_manager")
    return hack_manager.get_basic_property(hackathon, property_name, default_value)


Hackathon.is_auto_approve = is_auto_approve
Hackathon.is_pre_allocate_enabled = is_pre_allocate_enabled
Hackathon.get_pre_allocate_number = get_pre_allocate_number
Hackathon.is_alauda_enabled = is_alauda_enabled
Hackathon.get_basic_property = get_basic_property
