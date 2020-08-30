from time_series import TimeSeries
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

    def start(self, ui_callback=None):
        self._ui_callback = ui_callback
        self.data_source.start(self.flywheel_sensor_pulse_handler)

    def stop(self):
        self.data_source.stop()

    def flywheel_sensor_pulse_handler(self, sensor_pulse_time, raw_tick_value):
        self.raw_ticks.append(raw_tick_value)
        self.num_flywheel_revolutions += 1.0 / self.flywheel_metrics_tracker.NUM_ENCODER_PULSES_PER_REVOLUTION
        self.flywheel_sensor_pulse_timestamps.append(sensor_pulse_time)
        self.flywheel_metrics_tracker.update()
        # self._update_tick_stats()
        # Updates torque time series, check for the new stroke heuristic and updates the stroke time
        # series if needed.
        # self._update_torque_time_series()
        # if self._new_stroke_indicator():
        #     self._process_new_stroke()
        #     self._update_stroke_stats()


        self.stroke_metrics_tracker.update()

        if self._ui_callback is not None:
            self._ui_callback(self)


"""
    def _update_tick_stats(self):
        # Refresh stats that are updated for each rising edge event
        # total workout duration
        # instantaneous watts (averaged over some time period)
        # watt chart

        # Force curve
        # Total work done (boat distance)
        return

    def _update_stroke_stats(self):
        # Refresh stat that are updated for each stroke
        # Stroke rate
        return
"""

"""
    def save_workout(self, output_folder_path=""):
        # TODO: save raw ticks, clean ticks, speed, and acceleration
        timestamp = self.workout_start.strftime("%Y-%m-%d %Hh%Mm%Ss")
        output_file_name = timestamp + ".csv"
        output_file_path = os.path.append(output_folder_path, output_file_name)
        with open(output_file_path, "w", newline="") as output_file:
            csv_writer = csv.writer(output_file)
            csv_writer.writerow(
                [self.CSV_OUTPUT_TICKS_COLUMN_NAME, self.CSV_OUTPUT_SPEED_COLUMN_NAME, ]
            )
            for idx in range(len(self.speed)):
                csv_writer.writerow([self.speed[idx][1], self.speed[idx][0]])
"""
