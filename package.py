name = 'shotgun'

version = '1.11.0'

private_build_requires = ['rez_utils']

requires = [
    'python-2',
    'tk_shared_bundlecache',
    'rez',  # for resolving environments
]


def commands():
    # Export tank, sgtk and shotgun_api3 modules.
    env.PYTHONPATH.append('{root}/python/tk-core/python')
    env.PYTHONPATH.append('{root}/python/tk-core/python/tank_vendor')

    # Force shotgun to use out package files instead of the cloud.
    env.SGTK_DESKTOP_STARTUP_LOCATION = '{root}'

    env.SGTK_DISABLE_LEGACY_BROWSER_INTEGRATION_WORKAROUND = 1

    # By default, shotgun write it's cache in the home directory.
    # However in Linux, the home are mounted from the nas from result in unecessary io.
    # Note the user of the $USER variable. This ensure that each user will have it's own SHOTGUN_HOME.
    if system.platform == 'linux':
        env.SHOTGUN_HOME = '/var/tmp/shotgun/$USER'

    # todo: support other OS
    if system.platform == 'linux':
        env.PATH.append('/opt/Shotgun')
    elif system.platform == 'windows':
        env.PATH.append('C:/Program Files/Shotgun')

    # Use this flag to test change on the site configuration (id: 55) withouth disrupting the production.
    # env.TK_BOOTSTRAP_CONFIG_OVERRIDE = '/home/rlessard/packages/tk_config_squeeze/3.3.999'

    # Use this flag to increase the verbosity of the logger.
    # env.TK_DEBUG = 1
