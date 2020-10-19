from time_series import TimeSeries


class BoatModel:

    def __init__(self, workout):
        self.workout = workout
        self.position = TimeSeries()
        self.speed = TimeSeries()

    def update(self):
        """This function gets called on every flywheel encoder tick."""
        pass


class RotatingWheel(BoatModel):
    """A simple model to calculate boat speed and distance traveled. We assume the "boat" is just a wheel moving on
    the ground, with the same rotational speed as the rower's flywheel."""
    WHEEL_CIRCUMFERENCE_METERS = 1.0

    def update(self):
        if len(self.position) == 0:
            current_position = 0
        else:
            current_position = self.position.values[-1] + 1.0 / self.workout.machine.num_encoder_pulses_per_revolution
        self.position.append(
            value=current_position,
            timestamp=self.workout.machine.encoder_pulse_timestamps[-1]
        )

        if len(self.workout.machine.flywheel_speed) > 0:
            # Linear speed of a rolling wheel [m/s] = rotational speed [rev/s] * cirumference [m]
            boat_speed = self.workout.machine.flywheel_speed.values[-1] * self.WHEEL_CIRCUMFERENCE_METERS
            self.speed.append(
                value=boat_speed,
                timestamp=self.workout.machine.flywheel_speed.timestamps[-1]
            )

    # def get_total_distance(self, start_time=None, end_time=None):
    #     # Returns the distance moved between start_time and end_time. Returns distance since the beginning of workout
    #     # if both are null.
    #     if start_time is None:
    #         start_time = 0
    #     if end_time is None:
    #         end_time = self.workout.flywheel_sensor_pulse_timestamps[-1]
    #
    #     num_encoder_ticks_in_time_window = sum(
    #         [1 for x in self.workout.flywheel_sensor_pulse_timestamps if start_time <= x <= end_time]
    #     )
    #
    #     flywheel_revolutions = num_encoder_ticks_in_time_window / \
    #                            self.workout.flywheel_metrics_tracker.NUM_ENCODER_PULSES_PER_REVOLUTION
    #     return flywheel_revolutions * self.WHEEL_CIRCUMFERENCE_METERS

    # def get_average_speed(self, start_time=None, end_time=None):
    #     return
