"""Store common constants."""
MAJOR_VERSION = 0
MINOR_VERSION = 4
PATCH_VERSION = '0.dev0'
__version__ = '{}.{}.{}'.format(MAJOR_VERSION, MINOR_VERSION, PATCH_VERSION)

CONF_DATA = 'data'
CONF_ID = 'id'
CONF_TRIGGER = 'trigger'
CONFIG_DIR = 'config_dir'
JOB_ID = '--E{:02d}'
WELL_U_ID = '--U{:02d}'
WELL_V_ID = '--V{:02d}'
FIELD_X_ID = '--X{:02d}'
FIELD_Y_ID = '--Y{:02d}'
CHANNEL_ID = '--C{:02d}'
WELL_NAME = (WELL_U_ID + WELL_V_ID)[2:]
FIELD_NAME = (FIELD_X_ID + FIELD_Y_ID)[2:]
CONF_HOST = 'host'
CONF_PORT = 'port'
IMAGING_DIR = 'imaging_dir'
LOG_LEVEL = 'log_level'
WELL = 'well'
CONF_PLUGINS = 'plugins'
PACKAGE = 'camacq'

# events
BASE_EVENT = 'base_event'
CAMACQ_START_EVENT = 'camacq_start_event'
CAMACQ_STOP_EVENT = 'camacq_stop_event'
CHANNEL_EVENT = 'channel_event'
FIELD_EVENT = 'field_event'
IMAGE_REMOVED_EVENT = 'image_removed_event'
PLATE_EVENT = 'plate_event'
SAMPLE_EVENT = 'sample_event'
SAMPLE_IMAGE_EVENT = 'sample_image_event'
WELL_EVENT = 'well_event'
COMMAND_EVENT = 'command_event'
IMAGE_EVENT = 'image_event'
START_COMMAND_EVENT = 'start_command_event'
STOP_COMMAND_EVENT = 'stop_command_event'
