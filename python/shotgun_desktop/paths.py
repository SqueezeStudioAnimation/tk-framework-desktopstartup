# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import urlparse
import logging


def get_shotgun_app_root():
    """ returns where the shotgun app is installed """
    if sys.platform == "darwin":
        args = [os.path.dirname(__file__)] + [".."] * 5
        shotgun_root = os.path.abspath(os.path.join(*args))
    elif sys.platform == "win32":
        shotgun_root = os.path.abspath(os.path.dirname(sys.prefix))
    elif sys.platform.startswith("linux"):
        shotgun_root = os.path.abspath(os.path.dirname(sys.prefix))
    else:
        raise NotImplementedError("Unsupported platform: %s" % sys.platform)

    return shotgun_root


def get_python_path():
    """ returns the path to the default python interpreter """
    if sys.platform == "darwin":
        python = os.path.join(sys.prefix, "bin", "python")
    elif sys.platform == "win32":
        python = os.path.join(sys.prefix, "python.exe")
    elif sys.platform.startswith("linux"):
        python = os.path.join(sys.prefix, "bin", "python")
    return python


def get_default_site_config_root(connection):
    """ return the path to the default configuration for the site """
    # find what path field from the entity we need
    if sys.platform == "darwin":
        plat_key = "mac_path"
    elif sys.platform == "win32":
        plat_key = "windows_path"
    elif sys.platform.startswith("linux"):
        plat_key = "linux_path"
    else:
        raise RuntimeError("unknown platform: %s" % sys.platform)

    # interesting fields to return
    fields = ["id", "code", "windows_path", "mac_path", "linux_path", "project"]

    # Find either the pipeline configuration set with the template project
    # or the one without any project assigned. Note that is the both exist,
    # it will first return the one with the earliest project id. Sorting on project.Project.id
    # will first list in ascending project id order pipeline configurations with a project set
    # and then will list the remaining projects with an id. In case there is then
    # multiple pipeline configurations for a given project, we'll always take the first one.
    pcs = connection.find(
        "PipelineConfiguration",
        [{
            "filter_operator": "any",
            "filters": [
                ["project", "is", None],
                {
                    "filter_operator": "all",
                    "filters": [
                        ["project.Project.name", "is", "Template Project"],
                        ["project.Project.layout_project", "is", None]
                    ]
                }
            ]
        }],
        fields=fields,
        order=[
            {'field_name':'project.Project.id','direction':'asc'},
            {'field_name':'id','direction':'asc'}
        ]
    )

    if len(pcs) == 0:
        pc = None
    else:
        pc = pcs[0]
        # It is possible to get multiple pipeline configurations due to user error.
        # Log a warning if there was more than one pipeline configuration found.
        if len(pcs) > 1:
            logging.getLogger("tk-desktop.paths").info(
                "More than one pipeline configuration was found (%s), using %d" %
                (", ".join([str(p["id"]) for p in pcs]), pc["id"])
            )

    # see if we found a pipeline configuration
    if pc is not None and pc.get(plat_key, ""):
        # path is already set for us, just return it
        return (str(pc[plat_key]), pc)

    # get operating system specific root
    if sys.platform == "darwin":
        pc_root = os.path.expanduser("~/Library/Application Support/Shotgun")
    elif sys.platform == "win32":
        pc_root = os.path.join(os.environ["APPDATA"], "Shotgun")
    elif sys.platform.startswith("linux"):
        pc_root = os.path.expanduser("~/.shotgun")

    # add on site specific postfix
    site = __get_site_from_connection(connection)
    pc_root = os.path.join(pc_root, site, "site")

    return (str(pc_root), pc)


def __get_site_from_connection(connection):
    """ return the site from the information in the connection """
    # grab just the non-port part of the netloc of the url
    # eg site.shotgunstudio.com
    site = urlparse.urlparse(connection.base_url)[1].split(":")[0]
    return site
