import csv
import os
import datetime

from time_series import TimeSeries
import data_sources as ds
import rowing_stats

# MY_HARDWARE_SETUP = {
#     rpi ip = 192.168.1.242
#     rpi pigpiod port = 9876
#     rpi pin num = 17
#     rower type = magnetic
#     flywheel sensor pulses per rev = 4
#     flywheel sensor pulses are evenly spaced = false
# }


class WorkoutMetricsTracker:
    def __init__(
            self,
            data_source,
            flywheel_metrics_tracker_class=rowing_stats.FlywheelMetricsTracker,
            stroke_metrics_tracker_class=rowing_stats.StrokeMetricsTracker,
            damping_model_estimator_class=rowing_stats.LinearDampingFactorEstimator,
    ):
        self.data_source = data_source
        self.flywheel_metrics_tracker = flywheel_metrics_tracker_class(self)
        self.stroke_metrics_tracker = stroke_metrics_tracker_class(self)
        self.damping_model_estimator = damping_model_estimator_class(self)

        # We store the raw ticks for debugging and to facilitate future development.
        self.raw_ticks = []
        self.flywheel_sensor_pulse_timestamps = []
        self.num_flywheel_revolutions = 0
        self.speed = TimeSeries()
        self.acceleration = TimeSeries()
        self.torque = TimeSeries()
        self.strokes = TimeSeries()
        self._ui_callback = None
        self._qt_signal_emitter = None

    def start(self, ui_callback=None, qt_signal_emitter=None):
        self._ui_callback = ui_callback
        self._qt_signal_emitter = qt_signal_emitter
        self.data_source.start(self.flywheel_sensor_pulse_handler)

    def stop(self):
        self.data_source.stop()

    def flywheel_sensor_pulse_handler(self, sensor_pulse_time, raw_tick_value):
        self.raw_ticks.append(raw_tick_value)
        self.num_flywheel_revolutions += 1.0 / self.flywheel_metrics_tracker.NUM_ENCODER_PULSES_PER_REVOLUTION
        self.flywheel_sensor_pulse_timestamps.append(sensor_pulse_time)
        self.flywheel_metrics_tracker.update()
        self.stroke_metrics_tracker.update()

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
