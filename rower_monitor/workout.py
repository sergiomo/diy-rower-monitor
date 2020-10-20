import csv
import datetime
import os

from . import boat_metrics
from . import data_sources as ds
from . import machine_metrics
from . import person_metrics


class WorkoutMetricsTracker:
    def __init__(
            self,
            config,
            data_source,
            machine_metrics_tracker_class=machine_metrics.MachineMetricsTracker,
            person_metrics_tracker_class=person_metrics.PersonMetricsTracker,
            boat_model_class=boat_metrics.RotatingWheel,
    ):
        self.data_source = data_source

        self.machine = machine_metrics_tracker_class(
            workout=self,
            flywheel_moment_of_inertia=config.flywheel_moment_of_inertia,
            damping_model_estimator_class=config.damping_model_estimator_class,
            num_encoder_pulses_per_revolution=config.num_flywheel_encoder_pulses_per_revolution,
        )
        self.person = person_metrics_tracker_class(self)
        self.boat = boat_model_class(self)

        self._ui_callback = None
        self._qt_signal_emitter = None

    def start(self, ui_callback=None, qt_signal_emitter=None):
        self._ui_callback = ui_callback
        self._qt_signal_emitter = qt_signal_emitter
        self.data_source.start(self.flywheel_sensor_pulse_handler)

    def stop(self):
        self.data_source.stop()

    def flywheel_sensor_pulse_handler(self, sensor_pulse_time, raw_tick_value):
        self.machine.update(
            sensor_pulse_time=sensor_pulse_time,
            raw_tick_value=raw_tick_value
        )
        self.person.update()
        self.boat.update()

        if self._qt_signal_emitter is not None:
            self._qt_signal_emitter.updated.emit()
        elif self._ui_callback is not None:
            self._ui_callback(self)

    # TODO: change this to take in output_file_path -- decide file names within app.py
    def save(self, output_folder_path, output_file_name=None):
        if output_file_name is None:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %Hh%Mm%Ss")
            output_file_name = timestamp + ".csv"
        output_file_path = os.path.join(output_folder_path, output_file_name)
        with open(output_file_path, "w", newline="") as output_file:
            csv_writer = csv.writer(output_file)
            csv_writer.writerow(
                [ds.CsvFile.RAW_TICKS_COLUMN_NAME]
            )
            csv_writer.writerows([[x] for x in self.raw_ticks])
        return
