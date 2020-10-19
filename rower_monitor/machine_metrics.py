import numpy as np
from sklearn.linear_model import LinearRegression

from time_series import TimeSeries


class MachineMetricsTracker:
    def __init__(self,
                 workout,
                 flywheel_moment_of_inertia,
                 damping_model_estimator_class,
                 num_encoder_pulses_per_revolution):
        self.workout = workout
        self.num_encoder_pulses_per_revolution = num_encoder_pulses_per_revolution
        self.flywheel_moment_of_inertia = flywheel_moment_of_inertia

        self.raw_ticks = []
        self.encoder_pulse_timestamps = []
        self.flywheel_speed = TimeSeries()
        self.flywheel_acceleration = TimeSeries()

        self.damping_model_estimator = damping_model_estimator_class(workout)
        self.damping_models = []
        self.damping_torque = TimeSeries()
        self.strokes_seen = 0

    def update(self, sensor_pulse_time, raw_tick_value):
        self.update_flywheel_metrics(
            sensor_pulse_time=sensor_pulse_time,
            raw_tick_value=raw_tick_value
        )
        # There's a bit of a chicken-and-egg problem here between MachineMetricsTracker.update_damping_metrics (which
        # requires at least one stroke to be available) and PersonMetricsTracker.update (which requires at least one
        # damping torque sample. Both components will assume the damping torque is zero during the first stroke,
        # as a trade-off between accuracy and responsiveness.
        self.update_damping_metrics()

    def update_flywheel_metrics(self, sensor_pulse_time, raw_tick_value):
        self.raw_ticks.append(raw_tick_value)
        self.encoder_pulse_timestamps.append(sensor_pulse_time)
        self._update_speed_time_series()
        self._update_acceleration_time_series()

    def update_damping_metrics(self):
        new_stroke_info_available = len(self.workout.person.strokes) > self.strokes_seen
        if new_stroke_info_available:
            self.damping_models.append(
                self.damping_model_estimator.fit_model_to_stroke_recovery_data(
                    stroke=self.workout.person.strokes.values[-1]
                )
            )
            self.strokes_seen += 1
        self._update_damping_torque_time_series()

    def _update_speed_time_series(self):
        # Have we seen at least one full revolution?
        if len(self.encoder_pulse_timestamps) < self.NUM_ENCODER_PULSES_PER_REVOLUTION + 1:
            return
        speed_data_point, data_point_timestamp = self._get_speed_data_point_estimate()
        self.flywheel_speed.append(speed_data_point, data_point_timestamp)

    def _get_speed_data_point_estimate(self):
        # Account for the fact that the holes in the flywheel aren't perfectly aligned. We compute
        # speed by measuring the time between sensor pulses caused by the same hole. The unit of
        # these timestamps is seconds since the start of the workout.
        start_of_revolution_timestamp = self.encoder_pulse_timestamps[
            -1 * (self.NUM_ENCODER_PULSES_PER_REVOLUTION + 1)
        ]
        end_of_revolution_timestamp = self.encoder_pulse_timestamps[-1]
        # Compute the average speed observed in this revolution, in units of revolutions per second.
        revolution_time = end_of_revolution_timestamp - start_of_revolution_timestamp
        speed_data_point = 1.0 / revolution_time
        # We associate the average speed to a point in time right in the middle of the 2 flywheel
        # encoder pulses we used to measure the speed. This is consistent with an assumption that
        # the speed changes linearly.
        data_point_timestamp = (revolution_time / 2.0) + start_of_revolution_timestamp
        return speed_data_point, data_point_timestamp

    def _update_acceleration_time_series(self):
        if len(self.flywheel_speed) < 2:
            return
        (
            acceleration_data_point,
            data_point_timestamp,
        ) = self._get_acceleration_data_point_estimate()
        self.flywheel_acceleration.append(
            value=acceleration_data_point,
            timestamp=data_point_timestamp,
        )

    def _get_acceleration_data_point_estimate(self):
        speed_now_value, speed_now_timestamp = self.flywheel_speed[-1]
        previous_speed_value, previous_speed_timestamp = self.flywheel_speed[-2]
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

    def _update_damping_torque_time_series(self):
        if len(self.flywheel_speed) < 2:
            return
        # If we don't have a fitted model yet, assume the torque is zero
        if len(self.damping_models) < 1:
            damping_torque = 0.0
        else:
            speed_value = (self.flywheel_speed.values[-1] + self.flywheel_speed.values[-2]) / 2.0
            damping_acceleration = self.damping_models[-1].single_point(speed_value=speed_value)
            damping_torque = damping_acceleration * self.flywheel_moment_of_inertia
        self.damping_torque.append(
            value=damping_torque,
            timestamp=self.flywheel_acceleration.timestamps[-1]
        )


class MyMagneticRowerMetricsTracker(MachineMetricsTracker):
    # Tracks flywheel speed and acceleration. Assumes the encoder is not properly aligned.
    NUM_ENCODER_PULSES_PER_REVOLUTION = 4
    FLYWHEEL_MOMENT_OF_INTERTIA = 1.0

    def __init__(self, workout):
        super().__init__(
            workout=workout,
            flywheel_moment_of_inertia=self.FLYWHEEL_MOMENT_OF_INTERTIA,
            damping_model_estimator_class=LinearDampingFactorEstimator,
            num_encoder_pulses_per_revolution=self.NUM_ENCODER_PULSES_PER_REVOLUTION,
        )


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
        acceleration_samples_ts = self.workout.machine.flywheel_acceleration[
            stroke.start_of_recovery_idx: stroke.end_of_recovery_idx + 1
        ]
        # Speed has 1 extra sample at the beginning, and we include 1 extra sample at the end so we can interpolate
        # to match the acceleration time series timestamps.
        speed_samples_ts = self.workout.machine.flywheel_speed[
            stroke.start_of_recovery_idx: stroke.end_of_recovery_idx + 2
        ]
        # These are interpolated samples to align them time-wise with the acceleration time series.
        interpolated_speed_samples_ts = speed_samples_ts.interpolate_midpoints()
        included_acceleration_samples_ts = self.get_window(acceleration_samples_ts)
        # This is a very slow-speed stroke and there aren't enough samples to fit the damping model.
        if included_acceleration_samples_ts is None:
            # Try to return the same model as the previous stroke
            if len(self.workout.machine.damping_models) > 0:
                previous_model = self.workout.machine.damping_models[-1]
                return self.FittedLinearDampingFactorModel(
                    intercept=previous_model.intercept,
                    slope=previous_model.slope
                )
            # Return a model with all-zeros parameters. This will cause us to overestimate the person-applied torque
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
