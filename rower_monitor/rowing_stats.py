# MY_HARDWARE_SETUP = {
#     rpi ip = 192.168.1.242
#     rpi pigpiod port = 9876
#     rpi pin num = 17
#     rower type = magnetic
#     flywheel sensor pulses per rev = 4
#     flywheel sensor pulses are evenly spaced = false
# }


class TimeSeries:
    def __init__(self, values=[], timestamps=[]):
        self.values = values
        self.timestamps = timestamps

    def append(self, value, timestamp):
        self.values.append(value)
        self.timestamps.append(timestamp)

    def __getitem__(self, idx):
        if type(idx) is int:
            return (self.values[idx], self.timestamps[idx])
        elif type(idx) is slice:
            return TimeSeries(values=self.values[idx], timestamps=self.timestamps[idx])
        else:
            raise IndexError()

    def __len__(self):
        return len(self.values)

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return repr(self._dict__)


class WorkoutMetricsTracker:
    def __init__(self):
        self.data_source = PiGpioClient()
        self.flywheel_metrics_tracker = FlywheelMetricsTracker()
        self.stroke_metrics_tracker = StrokeMetricsTracker()

        # We store the raw ticks for debugging and to faciliate future development.
        self.raw_ticks = []
        self.flywheel_sensor_pulse_timestamps = []
        self.speed = TimeSeries()
        self.acceleration = TimeSeries()
        self.torque = TimeSeries()
        self.strokes = TimeSeries()
        self.ui_callback = None

    def start(self, ui_callback=None):
        self._ui_callback = ui_callback
        self.data_source.start(self.flywheel_sensor_pulse_handler)

    def stop(self):
        return

    def flywheel_sensor_pulse_handler(self, sensor_pulse_time, raw_tick_value):
        self.raw_ticks.append(raw_tick_value)
        self.flywheel_sensor_pulse_timestamps.append(sensor_pulse_time)
        self.flywheel_metrics_tracker.update(self)
        self.stroke_metrics_tracker.update(self)

        # self._update_speed_time_series(workout)
        # self._update_acceleration_time_series(workout)
        # self._update_torque_time_series()

        # self._update_tick_stats()

        # if self._new_stroke_indicator():
        #     self._process_new_stroke()
        #     self._update_stroke_stats()

        if self._ui_callback is not None:
            self._ui_callback(self)


# Tracks flywheel speed and acceleration. Assumes the encoder is not properly aligned.
class FlywheelMetricsTracker:
    NUM_ENCODER_PULSES_PER_REVOLUTION = 4

    def __init__(
        self,
        num_flywheel_sensor_pulses_per_revolution=self.NUM_ENCODER_PULSES_PER_REVOLUTION,
        flywheel_sensor_pulses_are_evenly_spaced=False,
    ):
        self.num_flywheel_sensor_pulses_per_revolution = (
            num_flywheel_sensor_pulses_per_revolution
        )
        pass

    def update(self, workout):
        self._update_speed_time_series(workout)
        self._update_acceleration_time_series(workout)

    def _update_speed_time_series(self, workout):
        # Have we seen at least one full revolution?
        if len(workout.raw_ticks) < self.NUM_ENCODER_PULSES_PER_REVOLUTION + 1:
            return
        speed_data_point, data_point_timestamp = self._get_speed_data_point_estimate(
            workout
        )
        workout.speed.append(speed_data_point, data_point_timestamp)

    def _get_speed_data_point_estimate(self, workout):
        # Account for the fact that the holes in the flywheel aren't evenly spaced. We compute
        # speed by measuring the time between sensor pulses caused by the same hole. The unit of
        # these timestamps is seconds since the start of the workout.
        start_of_revolution_timestamp = workout.raw_ticks[
            -1 * (self.NUM_ENCODER_PULSES_PER_REVOLUTION + 1)
        ]
        end_of_revolution_timestamp = workout.raw_ticks[-1]
        # Compute the average speed observed in this revolution, in units of revolutions per second.
        revolution_time = end_of_revolution_timestamp - start_of_revolution_timestamp
        speed_data_point = 1.0 / revolution_time
        # We associate the average speed to a point in time right in the middle of the 2 flywheel
        # encoder pulses we used to measure the speed. This is consistent with an assumption that
        # the speed changes linearly.
        data_point_timestamp = (revolution_time / 2.0) + start_of_revolution_timestamp
        return speed_data_point, data_point_timestamp

    def _update_acceleration_time_series(self, workout):
        if len(workout.speed) < 2:
            return
        (
            acceleration_data_point,
            data_point_timestamp,
        ) = self._get_acceleration_data_point_estimate(workout)
        workout.acceleration.append(
            acceleration_data_point, data_point_timestamp,
        )

    def _get_acceleration_data_point_estimate(self, workout):
        speed_now_value, speed_now_timestamp = workout.speed[-1]
        previous_speed_value, previous_speed_timestamp = workout.speed[-2]
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


####@@@@@@@@@@@@@@@@@@@@@@@@@


class StrokeMetricsTracker:
    # This is the filter, in seconds, that we apply when we detect the start of a new stroke.
    # It's probably safe to assume that the user will never reach 60 strokes per minute.
    MINIMUM_STROKE_DURATION_FILTER = 1.0

    def __init__(self):
        pass


class DampingFactorEstimator:
    def __init__(self):
        pass


# Used for magnetic rowers
class LinearRegressionDragFactorEstimator(DragFactorEstimator):
    def __init__(self):
        pass


class SimpleDragFractorEstimator(DragFactorEstimator):
    MAGNETIC_ROWER_POLYNOMIAL_ORDER = 1
    AIR_WATER_ROWER_POLYNOMIAL_ORDER = 2

    def __init__(self, polynomial_order=MAGNETIC_ROWER_POLYNOMIAL_ORDER):
        pass


class RowerMonitor:
    CSV_OUTPUT_TICKS_COLUMN_NAME = "ticks"
    CSV_OUTPUT_SPEED_COLUMN_NAME = "speed"

    def __init__(self, data_source):
        # Data source is either a pigpio session, or a CSV file path.
        self.data_source = data_source

        self.workout_start = None

        # Raw ticks as they come from the RPi. List of timestamps (tick counts).
        self.raw_ticks = []
        # Ticks adjusted to the first tick has a timestamp of 0, and corrected for the RPi counter rollover that occurs every ~72 minutes.
        # List of timestamps (microseconds since first tick).
        self.ticks = []
        # Flywheel speed in revolutions per second, corrected to account for the fact that the holes in the rower flywheel aren't evenly spaced.
        # List of tuples (speed, timestamp_in_seconds)
        self.speed = []
        # Flywheel accelration in rev / (s)^2
        # List of tuples (acceleration, timestamp_in_seconds)
        self.acceleration = []

        # List of tuples (torque, timestamp_in_seconds)
        self.torque = []

        self._start_of_last_stroke_timestamp = float("-inf")
        self._start_of_last_stroke_idx = 0
        self.strokes = []

        # Assume this is a CSV file path, load all data
        if type(data_source) == str:
            self.initialize_from_csv_data()

    def initialize_from_csv_data(self):
        # Process CSV, assumed to be raw ticks as written by self.save_workout()
        with open(self.data_source) as input_file:
            csv_reader = csv.DictReader(input_file)
            for row in csv_reader:
                tick = int(row[self.CSV_OUTPUT_TICKS_COLUMN_NAME])
                if tick == 0:
                    continue
                self.process_raw_sensor_pulse_event(tick)

    def _update_torque_time_series(self):
        if len(self.strokes) < 1:
            return
        fitted_model = self.strokes[-1][3]
        speed_now = (np.array(self.speed[-1][0]) + np.array(self.speed[-2][0])) / 2.0
        # TODO: single-source this
        X = np.array(speed_now).reshape(-1, 1)
        X_trans = PolynomialFeatures(1, include_bias=True).fit_transform(X)
        fitted = fitted_model.predict(X_trans)
        self.torque.append(
            (self.acceleration[-1][0] - fitted[0], self.acceleration[-1][1])
        )

    # This is a rough check that tells us if we have started a new stroke. This doesn't necessarily flag the first few samples of the new stroke.
    def _new_stroke_indicator(self):
        if len(self.acceleration) < 2:
            return False
        rising_edge = self.acceleration[-1][0] >= 0 and self.acceleration[-2][0] < 0
        time_between_strokes_in_seconds = (
            self.acceleration[-1][1] - self._start_of_last_stroke_timestamp
        )
        if (
            rising_edge
            and time_between_strokes_in_seconds > self.MINIMUM_STROKE_DURATION_FILTER
        ):
            return True
        else:
            return False

    def _calculate_stroke_damping_constant(self, first_sample_idx, last_sample_idx):
        # IDENTIFY DAMPING REGION:
        # 1. Select samples from end of pulse to when the acceleration becomes positive again
        # 2. Chop off the first and last ~15% of samples, this isolates the upwards ramp.
        CUTOFF_FRACTION = 0.01

        POLYNOMIAL_DEGREE = 1
        INTERCEPT = True

        acceleration_samples = self.acceleration[first_sample_idx : last_sample_idx + 1]
        # Speed has 2 extra samples at the beginning, and we include 1 extra sample at the start so we can interpolate
        speed_samples_raw = self.speed[first_sample_idx + 2 - 1 : last_sample_idx + 3]

        speed_samples = []
        for idx, data_point in enumerate(speed_samples_raw):
            if idx == len(speed_samples_raw) - 1:
                break
            a_value = data_point[0]
            a_time = data_point[1]
            b_value = speed_samples_raw[idx + 1][0]
            b_time = speed_samples_raw[idx + 1][1]
            speed_samples.append(((a_value + b_value) / 2.0, (a_time + b_time) / 2.0))

        last_falling_edge_time = None
        last_value = float("-inf")
        for idx, sample in enumerate(acceleration_samples):
            value, timestamp = sample
            if value < 0 and last_value >= 0:
                last_falling_edge_time = timestamp
            last_value = value

        window_size = speed_samples[-1][1] - last_falling_edge_time
        offset = window_size * CUTOFF_FRACTION
        min_time = last_falling_edge_time + offset
        max_time = speed_samples[-1][1] - offset

        # window_size = len(speed_samples) - 1 - last_falling_edge_idx
        # offset = int(window_size * CUTOFF_FRACTION)
        # start_idx = last_falling_edge_idx + offset
        # end_idx = len(speed_samples) - 1 - offset

        included_acceleration = []
        included_speed = []
        for idx, sample in enumerate(acceleration_samples):
            value, timestamp = sample
            if timestamp > min_time and timestamp < max_time:
                included_acceleration.append(value)
                included_speed.append(speed_samples[idx][0])

        # print(len(speed_samples), last_falling_edge_idx, start_idx, end_idx)

        # Acceleration as a function of speed
        X = np.array(included_speed).reshape(-1, 1)
        if len(included_speed) == 0:
            # TODO: if I rest right after completing a stroke, the last data point will be several seconds after the previous one.
            # This will cause the time-based selection function to select a time window for which we have no data points.
            print(window_size, min_time, max_time)
            print("\n".join([str(x) for x in speed_samples]))
            fig = plt.figure(
                figsize=(18, 6), dpi=80, facecolor="w", edgecolor="k", tight_layout=True
            )
            plt.plot(
                [x[1] for x in acceleration_samples],
                [x[0] for x in acceleration_samples],
            )
        X_trans = PolynomialFeatures(
            POLYNOMIAL_DEGREE, include_bias=INTERCEPT
        ).fit_transform(X)
        y = np.array(included_acceleration)
        reg = LinearRegression(fit_intercept=False).fit(X_trans, y)
        return reg, X, y

    def _process_new_stroke(self):
        # TODO: do fancy stats here to identify last credible sample that belongs to this stroke.
        # Do a linear regression, and find the first point that significantly deviates from the fitted line.

        last_sample_idx_of_previous_stroke = len(self.acceleration) - 2
        first_sample_idx_of_previous_stroke = self._start_of_last_stroke_idx
        num_samples_in_stroke = (
            last_sample_idx_of_previous_stroke - first_sample_idx_of_previous_stroke
        )

        # Append data about the stroke that just ended
        reg, X, y = self._calculate_stroke_damping_constant(
            first_sample_idx_of_previous_stroke, last_sample_idx_of_previous_stroke
        )
        self.strokes.append(
            (
                self.acceleration[first_sample_idx_of_previous_stroke][
                    1
                ],  # Start of stroke timestamp
                first_sample_idx_of_previous_stroke,  # Start of stroke idx (in self.acceleration)
                last_sample_idx_of_previous_stroke,
                reg,
                X,
                y,
            )
        )

        self._start_of_last_stroke_timestamp = self.acceleration[-1][1]
        self._start_of_last_stroke_idx = len(self.acceleration) - 1

        # Append to (or correct) force chart?

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

    def _update_speed_time_series(self):
        # Update speed time series
        if len(self.ticks) >= self.NUM_ENCODER_PULSES_PER_REVOLUTION + 1:
            # Account for the fact that the holes in the rower flywheel aren't evenly spaced.
            # We compute speed by measuring the time between pulses caused by the same hole.
            # The unit of these timestamps is seconds since start of workout.
            start_of_revolution_timestamp = (
                self.ticks[-1 * (self.NUM_ENCODER_PULSES_PER_REVOLUTION + 1)]
                / RASPBERRY_PI_TICKS_PER_SECOND
            )
            end_of_revolution_timestamp = self.ticks[-1] / RASPBERRY_PI_TICKS_PER_SECOND
            # Compute the average speed observed in this revolution, in units of revolutions per second.
            revolution_time = (
                end_of_revolution_timestamp - start_of_revolution_timestamp
            )
            speed_data_point = 1.0 / revolution_time
            data_point_timestamp = (
                revolution_time / 2.0
            ) + start_of_revolution_timestamp
            self.speed.append((speed_data_point, data_point_timestamp))

    def _update_acceleration_time_series(self):
        # Acceleration time series
        self._calculate_derivate_of_time_series(
            source_time_series=self.speed, target_time_series=self.acceleration
        )
        """
        if len(self.speed) > 2:
            speed_now_tuple = self.speed[-1]
            previous_speed_tuple = self.speed[-2]
            speed_delta = speed_now_tuple[0] - previous_speed_tuple[0]
            time_delta = (speed_now_tuple[1] - previous_speed_tuple[1])
            #Compute average acceleration observed in this time period, in units of rev / (s)^2
            acceleration_data_point = speed_delta / time_delta
            data_point_timestamp = (time_delta / 2) + previous_speed_tuple[1]
            self.acceleration.append((
                acceleration_data_point,
                data_point_timestamp,
            ))
        """

    def _calculate_derivate_of_time_series(
        self, source_time_series, target_time_series
    ):
        if len(source_time_series) > 2:
            value_now_tuple = source_time_series[-1]
            previous_value_tuple = source_time_series[-2]
            value_delta = value_now_tuple[0] - previous_value_tuple[0]
            time_delta = value_now_tuple[1] - previous_value_tuple[1]
            # Compute average acceleration observed in this time period, in units of rev / (s)^2
            derivative_data_point = value_delta / time_delta
            data_point_timestamp = (time_delta / 2.0) + previous_value_tuple[1]
            target_time_series.append((derivative_data_point, data_point_timestamp,))

    def save_workout(self, output_folder_path=""):
        # TODO: save raw ticks, clean ticks, speed, and acceleration
        timestamp = self.workout_start.strftime("%Y-%m-%d %Hh%Mm%Ss")
        output_file_name = timestamp + ".csv"
        output_file_path = os.path.append(output_folder_path, output_file_name)
        with open(output_file_path, "w", newline="") as output_file:
            csv_writer = csv.writer(output_file)
            csv_writer.writerow(
                [self.CSV_OUTPUT_TICKS_COLUMN_NAME, self.CSV_OUTPUT_SPEED_COLUMN_NAME,]
            )
            for idx in range(len(self.speed)):
                csv_writer.writerow([self.speed[idx][1], self.speed[idx][0]])
