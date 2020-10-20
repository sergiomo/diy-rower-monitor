from .time_series import TimeSeries


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
