class RotatingWheel:
    """A simple model to calculate boat speed and distance traveled. We assume the "boat" is just a wheel moving on
    the ground, with the same rotational speed as the rower's flywheel."""
    WHEEL_CIRCUMFERENCE_METERS = 1.0

    def __init__(self, workout):
        self.workout = workout

    def event_handler(self):
        # Whenever there's a new tick from the encoder:
        #  1. Update the boat distance time series
        #  2. Update the boat speed time series (this is a scaled version of the

        #self.workout.boat_distance = blaa
        #self.workout.boat_speed = blaa
        #self.workout.boat_acceleration = blaa
        return

    def get_total_distance(self, start_time=None, end_time=None):
        # Returns the distance moved between start_time and end_time. Returns distance since the beginning of workout
        # if both are null.
        if start_time is None:
            start_time = 0
        if end_time is None:
            end_time = self.workout.flywheel_sensor_pulse_timestamps[-1]

        num_encoder_ticks_in_time_window = sum(
            [1 for x in self.workout.flywheel_sensor_pulse_timestamps if start_time <= x <= end_time]
        )

        flywheel_revolutions = num_encoder_ticks_in_time_window / \
                               self.workout.flywheel_metrics_tracker.NUM_ENCODER_PULSES_PER_REVOLUTION
        return flywheel_revolutions * self.WHEEL_CIRCUMFERENCE_METERS

    def get_average_speed(self, start_time=None, end_time=None):
        return
