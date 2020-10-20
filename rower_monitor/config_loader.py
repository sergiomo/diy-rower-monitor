import os
import pathlib
import yaml
from collections import namedtuple

from . import machine_metrics

CONFIG_FILE_PATH = os.path.join(pathlib.Path(__file__).parent.absolute(), 'my_config.yaml')

DAMPING_MODEL_ESTIMATOR_CLASS_LOOKUP = {
    'magnetic': machine_metrics.LinearDampingFactorEstimator,
}

Config = namedtuple(
    typename='Config',
    field_names=[
        'ip_address',
        'pigpio_daemon_port',
        'gpio_pin_numer',
        'num_flywheel_encoder_pulses_per_revolution',
        'machine_type',
        'flywheel_moment_of_inertia',
        'log_folder_path',
        'damping_model_estimator_class'
    ])


def load_config():
    with open(CONFIG_FILE_PATH) as input_file:
        config_data = yaml.load(input_file, Loader=yaml.FullLoader)
        args = {}
        for section_name, mapping in config_data.items():
            args.update(mapping)
        args['damping_model_estimator_class'] = DAMPING_MODEL_ESTIMATOR_CLASS_LOOKUP[args['machine_type'].lower()]
        return Config(**args)