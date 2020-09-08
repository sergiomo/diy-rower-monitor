import numpy as np
from sklearn.linear_model import LinearRegression

from time_series import TimeSeries


class FlywheelMetricsTracker:
    # Tracks flywheel speed and acceleration. Assumes the encoder is not properly aligned.
    NUM_ENCODER_PULSES_PER_REVOLUTION = 4

    def __init__(
            self,
            workout,
            num_flywheel_sensor_pulses_per_revolution=NUM_ENCODER_PULSES_PER_REVOLUTION,
    ):
        self.workout = workout
        self.num_flywheel_sensor_pulses_per_revolution = (
            num_flywheel_sensor_pulses_per_revolution
        )

    def update(self):
        self._update_speed_time_series()
        self._update_acceleration_time_series()

    def _update_speed_time_series(self):
        # Have we seen at least one full revolution?
        if len(self.workout.flywheel_sensor_pulse_timestamps) < self.NUM_ENCODER_PULSES_PER_REVOLUTION + 1:
            return
        speed_data_point, data_point_timestamp = self._get_speed_data_point_estimate()
        self.workout.speed.append(speed_data_point, data_point_timestamp)

    def _get_speed_data_point_estimate(self):
        # Account for the fact that the holes in the flywheel aren't perfectly aligned. We compute
        # speed by measuring the time between sensor pulses caused by the same hole. The unit of
        # these timestamps is seconds since the start of the workout.
        start_of_revolution_timestamp = self.workout.flywheel_sensor_pulse_timestamps[
            -1 * (self.NUM_ENCODER_PULSES_PER_REVOLUTION + 1)
        ]
        end_of_revolution_timestamp = self.workout.flywheel_sensor_pulse_timestamps[-1]
        # Compute the average speed observed in this revolution, in units of revolutions per second.
        revolution_time = end_of_revolution_timestamp - start_of_revolution_timestamp
        speed_data_point = 1.0 / revolution_time
        # We associate the average speed to a point in time right in the middle of the 2 flywheel
        # encoder pulses we used to measure the speed. This is consistent with an assumption that
        # the speed changes linearly.
        data_point_timestamp = (revolution_time / 2.0) + start_of_revolution_timestamp
        return speed_data_point, data_point_timestamp

    def _update_acceleration_time_series(self):
        if len(self.workout.speed) < 2:
            return
        (
            acceleration_data_point,
            data_point_timestamp,
        ) = self._get_acceleration_data_point_estimate()
        self.workout.acceleration.append(
            value=acceleration_data_point,
            timestamp=data_point_timestamp,
        )

    def _get_acceleration_data_point_estimate(self):
        speed_now_value, speed_now_timestamp = self.workout.speed[-1]
        previous_speed_value, previous_speed_timestamp = self.workout.speed[-2]
        speed_delta = speed_now_value - previous_speed_value
        time_delta = speed_now_timestamp - previous_speed_timestamp
        # Compute average acceleration observed in this time period, in units of rev / (s)^2
        acceleration_data_point = speed_delta / time_delta
        # We associate the average acceleration to a point in time right in the middle of the 2
        # speed data points we used to measure the acceleration. This -- plus the assumption that
        # speed is linear w.r.t. time -- is consistent with an assumption that acceleration was
        # constant during this revolution.
        data_point_timestamp = (time_delta / 2) + previous_speed_timestamp
        return acceleration_data_point, data_point_timestamp


class StrokeMetricsTracker:
    # This is the filter, in seconds, that we apply when we detect the start of a new stroke.
    # It's probably safe to assume that the user will never reach 60 strokes per minute.
    MINIMUM_STROKE_DURATION_FILTER = 1.0
    FLYWHEEL_MOMENT_OF_INERTIA = 1.0

    def __init__(self, workout):
        self.workout = workout
        self._start_of_ongoing_stroke_timestamp = float("-inf")
        self._start_of_ongoing_stroke_idx = 0

    def update(self):
        # Are we at the start of a new stroke? If so, analyze the data and update the stroke time
        # series, if not return without doing anything.
        if self._new_stroke_indicator():
            self._process_new_stroke()

        if len(self.workout.acceleration) < 1:
            return
        if len(self.workout.strokes) > 0:
            # Calculate rower_acc = net_acc - damping_acc
            last_fitted_model = self.workout.strokes.values[-1].fitted_damping_model
            speed_value = (self.workout.speed.values[-1] + self.workout.speed.values[-2]) / 2.0
            flywheel_deceleration_due_to_damping = last_fitted_model.single_point(speed_value)
        else:
            flywheel_deceleration_due_to_damping = 0.0
        person_acc = max(0.0, self.workout.acceleration.values[-1] - flywheel_deceleration_due_to_damping)
        self.workout.torque.append(
            value=person_acc,
            timestamp=self.workout.acceleration.timestamps[-1]
        )

    # This is a rough check that tells us if we have started a new stroke. This doesn't necessarily
    # flag the first few samples of the new stroke.
    def _new_stroke_indicator(self):
        if len(self.workout.acceleration) < 2:
            return False
        # Acceleration went from negative to positive
        acceleration_rising_edge = (
            self.workout.acceleration.values[-1] >= 0 and
            self.workout.acceleration.values[-2] < 0
        )
        time_since_start_of_stroke_in_seconds = (
            self.workout.acceleration.timestamps[-1] - self._start_of_ongoing_stroke_timestamp
        )
        return acceleration_rising_edge and \
            (time_since_start_of_stroke_in_seconds > self.MINIMUM_STROKE_DURATION_FILTER)

    def _process_new_stroke(self):
        # For now assume _new_stroke_indicator gives us a perfect segmentation between strokes, and
        # triggers exactly on the first sample of a new stroke.
        start_of_this_stroke_idx = self._start_of_ongoing_stroke_idx
        end_of_this_stroke_idx = len(self.workout.acceleration) - 2

        self.workout.strokes.append(
            value=Stroke(
                workout=self.workout,
                start_idx=start_of_this_stroke_idx,
                end_idx=end_of_this_stroke_idx,
            ),
            timestamp=self.workout.acceleration.timestamps[start_of_this_stroke_idx],
        )
        # The last sample currently in the acceleration time series will be the first sample of the
        # next stroke.
        self._start_of_ongoing_stroke_idx = len(self.workout.acceleration) - 1
        # fmt: off
        self._start_of_ongoing_stroke_timestamp = self.workout.acceleration.timestamps[-1]
        # fmt: on


class Stroke:
    def __init__(self,
                 workout,
                 start_idx,
                 end_idx):
        self.workout = workout
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.num_samples = end_idx - start_idx

        (self.start_of_drive_idx,
         self.end_of_drive_idx,
         self.start_of_recovery_idx,
         self.end_of_recovery_idx) = self._segment_stroke()

        self.fitted_damping_model = (
            self.workout.damping_model_estimator.fit_model_to_stroke_recovery_data(self)
        )
        self.duration = self.workout.acceleration.timestamps[end_idx] - self.workout.acceleration.timestamps[start_idx]

        drive_duration = self.workout.acceleration.timestamps[self.end_of_drive_idx] - \
                         self.workout.acceleration.timestamps[self.start_of_drive_idx]
        recovery_duration = self.duration - drive_duration
        # Ratio is 2:1 when recovery is twice as long as drive
        self.recovery_to_drive_ratio = recovery_duration / drive_duration

    def _segment_stroke(self):
        acceleration_samples = self.workout.acceleration[self.start_idx: self.end_idx].values
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

    def estimate_damping_deceleration(self, speed_value):
        return self.fitted_damping_model.single_point(speed_value)


class LinearDampingFactorEstimator:

    class FittedLinearDampingFactorModel:
        def __init__(self, intercept, slope):
            self.intercept = intercept
            self.slope = slope

        def single_point(self, speed_value):
            # Returns the expected flywheel acceleration due to the damping force.
            return self.intercept + self.slope * speed_value

    def __init__(self, workout):
        self.workout = workout

    def fit_model_to_stroke_recovery_data(self, stroke):
        acceleration_samples_ts = self.workout.acceleration[
            stroke.start_of_recovery_idx: stroke.end_of_recovery_idx + 1
        ]
        # Speed has 1 extra sample at the beginning, and we include 1 extra sample at the start so we can interpolate
        # to match the acceleration time series timestamps.
        speed_samples_ts = self.workout.speed[
            stroke.start_of_recovery_idx: stroke.end_of_recovery_idx + 2
        ]
        # These are interpolated samples to align them time-wise with the acceleration time series.
        interpolated_speed_samples_ts = TimeSeries()
        for idx, (value, timestamp) in enumerate(speed_samples_ts):
            if idx == len(speed_samples_ts) - 1:
                break
            next_value_in_ts, next_timestamp_in_ts = speed_samples_ts[idx + 1]
            interpolated_speed_samples_ts.append(
                value=(value + next_value_in_ts) / 2.0,
                timestamp=(timestamp + next_timestamp_in_ts) / 2.0)
        included_acceleration_samples_ts = self.get_window(acceleration_samples_ts)
        # This is a very slow-speed stroke and there aren't enough samples to fit the damping model.
        if included_acceleration_samples_ts is None:
            # Try to return the same model as the previous stroke
            if len(self.workout.strokes) > 0:
                previous_stroke = self.workout.strokes.values[-1]
                return self.FittedLinearDampingFactorModel(
                    intercept=previous_stroke.fitted_damping_model.intercept,
                    slope=previous_stroke.fitted_damping_model.slope
                )
            # Return a model wil all-zeros parameters. This will cause us to overestimate the person-applied torque
            # for this stroke. This is a very slow and weak stroke so this shouldn't matter too much.
            else:
                return self.FittedLinearDampingFactorModel(
                    intercept=0.0,
                    slope=0.0
                )
        included_speed_samples_ts = interpolated_speed_samples_ts.get_time_slice(
            start_time=included_acceleration_samples_ts.timestamps[0],
            end_time=included_acceleration_samples_ts.timestamps[-1]
        )
        # Acceleration as a function of speed
        y = np.array(included_acceleration_samples_ts.values)
        X = np.array(included_speed_samples_ts.values).reshape(-1, 1)
        fitted_linear_regression_model = LinearRegression(fit_intercept=True).fit(X, y)

        return self.FittedLinearDampingFactorModel(
            intercept=fitted_linear_regression_model.intercept_,
            slope=fitted_linear_regression_model.coef_[0]
        )

    def get_window(self, acceleration_samples_ts):
        """Here is where we select a subset of the recovery phase data points to fit our model to."""
        MIN_NUM_SAMPLES = 3
        CUTOFF_FRACTION = 0.25

        # The recovery phase contains exactly the minimum number of samples required to fit a reasonable model.
        # Return the input time series as-is.
        if len(acceleration_samples_ts) == MIN_NUM_SAMPLES:
            return acceleration_samples_ts
        # There are less than the minimum number of samples in the recovery phase (which can happen if speed is very
        # low). Return None and let the upper levels of software decide what to do.
        elif len(acceleration_samples_ts) < MIN_NUM_SAMPLES:
            return None

        # If there's a very long delay between the end of this stroke's drive and the beginning of the next one,
        # the time window might not include any actual observed data points. Say the recovery time is 12 seconds but
        # the flywheel was stopped for 10 seconds so there's a 10-second gap between the last and second-to-last data
        # points in the time series. Here we iteratively drop the last sample of the recovery phase until the middle
        # 50% window includes sufficient data points to fit a reasonable model to.
        result = TimeSeries()
        last_sample_to_consider_idx = -1
        while len(result) <= MIN_NUM_SAMPLES:
            # Measure recovery time
            start_of_recovery_timestamp = acceleration_samples_ts.timestamps[0]
            end_of_recovery_timestamp = acceleration_samples_ts.timestamps[last_sample_to_consider_idx]
            recovery_time_duration = start_of_recovery_timestamp - end_of_recovery_timestamp
            # Calculate candidate time window
            offset = recovery_time_duration * CUTOFF_FRACTION
            min_time = start_of_recovery_timestamp + offset
            max_time = end_of_recovery_timestamp - offset
            result = acceleration_samples_ts.get_time_slice(min_time, max_time)
            # Drop the last sample if the candidate time window didn't include enough data points.
            last_sample_to_consider_idx -= 1
        # Return if the candidate passed the length test
        return result
