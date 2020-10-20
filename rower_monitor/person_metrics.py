from .time_series import TimeSeries


class Stroke:
    def __init__(self,
                 workout,
                 start_idx,
                 end_idx):
        self.workout = workout
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.num_samples = end_idx - start_idx


        self.start_time = self.workout.machine.flywheel_acceleration.timestamps[start_idx]
        self.end_time = self.workout.machine.flywheel_acceleration.timestamps[end_idx]

        (self.start_of_drive_idx,
         self.end_of_drive_idx,
         self.start_of_recovery_idx,
         self.end_of_recovery_idx) = self._segment_stroke()

        self.duration = self.end_time - self.start_time
        drive_duration = self.workout.machine.flywheel_acceleration.timestamps[self.end_of_drive_idx] - \
                         self.workout.machine.flywheel_acceleration.timestamps[self.start_of_drive_idx]
        recovery_duration = self.duration - drive_duration
        # Ratio is 2:1 when recovery is twice as long as drive
        self.recovery_to_drive_ratio = recovery_duration / drive_duration
        self.work_done_by_person = self._calculate_work_done_by_person()
        self.average_power = self.work_done_by_person / self.duration

    def _segment_stroke(self):
        acceleration_samples = self.workout.machine.flywheel_acceleration[self.start_idx: self.end_idx].values
        min_acceleration_value = min(acceleration_samples)
        # Get the index (relative to workout.acceleration) of the last occurrence of the smallest acceleration value
        # in this stroke.
        min_acceleration_value_idx = self.start_idx \
            + len(acceleration_samples) \
            - acceleration_samples[::-1].index(min_acceleration_value)
        start_of_drive_idx = self.start_idx
        end_of_drive_idx = min_acceleration_value_idx
        start_of_recovery_idx = min_acceleration_value_idx + 1
        end_of_recovery_idx = self.end_idx
        return (start_of_drive_idx, end_of_drive_idx, start_of_recovery_idx, end_of_recovery_idx)

    def _calculate_work_done_by_person(self):
        """Calculates the work done by the person who's rowing.
                           Work_person = torque_person * angular distance
        We calculate the total work done during this stroke via numeric integration of
                          delta_work = instantaneous_torque * delta_theta
        (Below we assume the flywheel speed is constant between ticks)"""
        torque_samples_ts = self.workout.person.torque[self.start_idx: self.end_idx + 1]
        # Speed has 1 extra sample at the beginning, and we include 1 extra sample at the end so we can interpolate
        # to match the acceleration time series timestamps. We also include an additional look-ahead sample at the end
        # to calculate the rotational distance traveled in the last time differential.
        speed_samples_ts = self.workout.machine.flywheel_speed[self.start_idx: self.end_idx + 3]
        # These are interpolated samples to align them time-wise with the torque time series.
        interpolated_speed_samples_ts = speed_samples_ts.interpolate_midpoints()
        # Numeric integration
        result = 0.0
        for idx, (torque_value, timestamp) in enumerate(torque_samples_ts):
            instantaneous_speed = (interpolated_speed_samples_ts.values[idx] + interpolated_speed_samples_ts.values[idx + 1]) / 2.0
            # This is why we need an extra look-ahead sample at the tail end of the speed time series.
            next_timestamp = interpolated_speed_samples_ts.timestamps[idx + 1]
            time_between_samples = next_timestamp - timestamp
            delta_distance = instantaneous_speed * time_between_samples
            result += delta_distance * torque_value
        return result


class PersonMetricsTracker:
    # This is the filter, in seconds, that we apply when we detect the start of a new stroke.
    # It's probably safe to assume that the user will never reach 60 strokes per minute.
    MINIMUM_STROKE_DURATION_FILTER = 1.0

    def __init__(self, workout):
        self.workout = workout

        self.torque = TimeSeries()
        self.strokes = TimeSeries()

        self._start_of_ongoing_stroke_timestamp = float("-inf")
        self._start_of_ongoing_stroke_idx = 0

    def update(self):
        # Are we at the start of a new stroke? If so, analyze the data and update the stroke time
        # series, if not return without doing anything.
        if self._new_stroke_indicator():
            self._process_new_stroke()

        if len(self.workout.machine.flywheel_acceleration) < 1:
            return

        net_torque = self.workout.machine.flywheel_acceleration.values[-1] * self.workout.machine.flywheel_moment_of_inertia
        if len(self.workout.machine.damping_torque) > 0:
            damping_torque = self.workout.machine.damping_torque.values[-1]
            assert self.workout.machine.flywheel_acceleration.timestamps[-1] == \
                   self.workout.machine.damping_torque.timestamps[-1], "Flywheel acceleration and damping torque time " \
                                                                       "series aren't aligned! "
        else:
            damping_torque = 0
        person_torque = max(net_torque - damping_torque, 0.0)
        self.torque.append(
            value=person_torque,
            timestamp=self.workout.machine.flywheel_acceleration.timestamps[-1]
        )

    # This is a rough check that tells us if we have started a new stroke. This doesn't necessarily
    # flag the first few samples of the new stroke.
    def _new_stroke_indicator(self):
        if len(self.workout.machine.flywheel_acceleration) < 2:
            return False
        # Acceleration went from negative to positive
        acceleration_rising_edge = (
            self.workout.machine.flywheel_acceleration.values[-1] >= 0 and
            self.workout.machine.flywheel_acceleration.values[-2] < 0
        )
        time_since_start_of_stroke_in_seconds = (
            self.workout.machine.flywheel_acceleration.timestamps[-1] - self._start_of_ongoing_stroke_timestamp
        )
        return acceleration_rising_edge and \
            (time_since_start_of_stroke_in_seconds > self.MINIMUM_STROKE_DURATION_FILTER)

    def _process_new_stroke(self):
        # For now assume _new_stroke_indicator gives us a perfect segmentation between strokes, and
        # triggers exactly on the first sample of a new stroke.
        # TODO: more sophisticated segmentation by finding the last "credible data point" belonging to a stroke,
        #  identified by looking at the model fit residuals. For each point calculate the p value and set a cut-off
        #  threshold.
        start_of_this_stroke_idx = self._start_of_ongoing_stroke_idx
        end_of_this_stroke_idx = len(self.workout.machine.flywheel_acceleration) - 2

        self.strokes.append(
            value=Stroke(
                workout=self.workout,
                start_idx=start_of_this_stroke_idx,
                end_idx=end_of_this_stroke_idx,
            ),
            timestamp=self.workout.machine.flywheel_acceleration.timestamps[start_of_this_stroke_idx],
        )
        # The last sample currently in the acceleration time series will be the first sample of the
        # next stroke.
        self._start_of_ongoing_stroke_idx = len(self.workout.machine.flywheel_acceleration) - 1
        self._start_of_ongoing_stroke_timestamp = self.workout.machine.flywheel_acceleration.timestamps[-1]
