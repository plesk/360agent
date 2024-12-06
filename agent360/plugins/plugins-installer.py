#!/usr/bin/env python
# -*- coding: utf-8 -*-
import plugins
import os
import glob
import sys
import ssl
import certifi
import logging
import json
from pprint import pprint

if sys.version_info >= (3,):
    import http.client
    import configparser
    try:
        from past.builtins import basestring
    except ImportError:
        basestring = str
else:
    import httplib
    import ConfigParser as configparser


config_path = os.path.join('/etc', 'agent360.ini')

if os.name == 'nt':
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'agent360.ini')

class Plugin(plugins.BasePlugin):
    __name__ = 'plugins-installer'

    def run(self, config):
        self.config = config
        self.check_plugins_backend_state('http')
        results = self._get_plugins()
        return results

    def check_plugins_backend_state(self, proto='https'):
        server = self.config.get('agent', 'server')
        user = self.config.get('agent', 'user')

        body = {'userId': user, 'serverId': server}
        try:
            connection = self._get_connection(proto)
            connection.request('POST', '/plugin-manager/get-backend-state',  str(json.dumps(body)).encode())
            response = connection.getresponse()

            if response.status == 200:
                logging.debug('Successful response: %s', response.status)
            else:
                raise ValueError('Unsuccessful response: %s' % response.status)

            backend_state = json.loads(response.read().decode())
            for plugin in backend_state:
                for c in plugin['config']:
                    self._set_plugin_state(plugin['id'], c, plugin['config'][c])
        except Exception as e:
            logging.error('Failed to get plugins state: %s' % e)

    def _get_connection(self, proto):
        api_host = self.config.get('data', 'api_host')
        if (proto == 'https'):
            ctx = ssl.create_default_context(cafile=certifi.where())
            if sys.version_info >= (3,):
                return http.client.HTTPSConnection(api_host, context=ctx, timeout=15)
            else:
                return httplib.HTTPSConnection(api_host, context=ctx, timeout=15)
        else:
            if sys.version_info >= (3,):
                return http.client.HTTPConnection(api_host, timeout=15)
            else:
                return httplib.HTTPConnection(api_host, timeout=15)

    def _get_plugins_path(self):
        if os.name == 'nt':
            return os.path.expandvars(self.config.get('agent', 'plugins'))
        else:
            return self.config.get('agent', 'plugins')

    def _get_plugins(self):
        plugins_path = self._get_plugins_path()
        plugins = {}
        for filename in glob.glob(os.path.join(plugins_path, '*.py')):
            plugin_name = self._plugin_name(filename)
            if plugin_name == 'plugins' or plugin_name == '__init__':
                continue
            self._config_section_create(plugin_name)
            state = 0
            if self.config.getboolean(plugin_name, 'enabled'):
                state = 1
            plugins[plugin_name] =  self._get_section_properties(plugin_name)

        return plugins

    def _plugin_name(self, plugin):
        if isinstance(plugin, basestring):
            basename = os.path.basename(plugin)
            return os.path.splitext(basename)[0]
        else:
            return plugin.__name__

    def _config_section_create(self, section):
        if not self.config.has_section(section):
            self.config.add_section(section)

    def _set_plugin_state(self, plugin, key, value):
        config = configparser.ConfigParser(allow_no_value=True)
        config.read(config_path)

        if plugin not in config.sections():
            config.add_section(plugin)

        config.set(plugin, key, value)

        with open(config_path, 'w') as file:
            config.write(file)

    def _get_section_properties(self, section_name):
        config = configparser.ConfigParser(default_section=None)
        config.read(config_path)

        if section_name in config:
            properties = {key: config[section_name][key] for key in config.options(section_name) if key in config[section_name]}
            return dict(properties)
        else:
            return {}

if __name__ == '__main__':
    Plugin().execute()