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
import fnmatch
import cPickle

from .action_base import Action
from ...errors import TankError
from ...util import yaml_cache

class CacheYamlAction(Action):
    """
    Action that ensures that crawls a config, caching all YAML data found
    to disk as pickled data.
    """
    def __init__(self):
        Action.__init__(
            self, 
            "cache_yaml", 
            Action.TK_INSTANCE, 
            "Populates a cache of all YAML data found in the config.",
            "Admin",
        )
    
        # this method can be executed via the API
        self.supports_api = True
        
    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor. 
        Called when someone runs a tank command through the core API.
        
        This command takes no parameters, so an empty dictionary 
        should be passed. The parameters argument is there because
        we are deriving from the Action base class which requires 
        this parameter to be present.
        
        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """
        return self._run(log)
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        
        :param log: std python logger
        :param args: command line args
        """
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        return self._run(log)
        
    def _run(self, log):
        """
        Actual execution payload
        """         
        log.info("This command will traverse the entire configuration and build a "
                 "cache of all YAML data found.")

        root_dir = self.tk.pipeline_configuration.get_path()

        matches = []
        for root, dir_names, file_names in os.walk(root_dir):
            for file_name in fnmatch.filter(file_names, "*.yml"):
                matches.append(os.path.join(root, file_name))
        for path in matches:
            yaml_cache.g_yaml_cache.get(path)

        items = yaml_cache.g_yaml_cache.get_cached_items()
        pickle_path = os.path.join(root_dir, "yaml_cache.pickle")

        try:
            fh = open(pickle_path, "wb")
        except Exception, e:
            raise TankError("Unable to open '%s' for writing: %s" % (pickle_path, e))

        try:
            cPickle.dump(items, fh)
        except Exception, e:
            raise TankError("Unable to dump pickled cache data: %s" % e)

        log.info("")
        log.info("Cache yaml completed!")
