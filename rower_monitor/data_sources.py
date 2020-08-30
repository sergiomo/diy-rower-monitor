import csv
import pigpio
import time
import threading

class DataSource:
    def __init__(self):
        pass

    def start(self, sensor_pulse_event_handler_callback):
        pass

    def stop(self):
        pass


class PiGpioClient(DataSource):
    # The maximum number of ticks that the Raspberry Pi can count up to before rolling over.
    # Constant taken from https://github.com/joan2937/pigpio/blob/v76/pigpio.py#L961
    RPI_TIMER_MAX_VALUE = 1 << 32
    RPI_TICK_PERIOD_IN_SECONDS = 1e-6
    RPI_IP_ADDRESS = "192.168.1.242"
    RPI_PIGPIO_PORT = 9876
    RPI_PIN_NUMBER = 17

    # The reflective infrared sensor does not have hysteresis, so we need to filter out glitches in
    # software.
    GLITCH_FILTER_US = 1000

    def __init__(
        self,
        ip_address=RPI_IP_ADDRESS,
        pigpio_port=RPI_PIGPIO_PORT,
        gpio_pin_number=RPI_PIN_NUMBER,
        glitch_filter_us=GLITCH_FILTER_US,
    ):
        self.ip_address = ip_address
        self.pigpio_port = pigpio_port
        self.gpio_pin_number = gpio_pin_number
        self.glitch_filter_us = glitch_filter_us
        self._first_raw_tick_value = None
        self._last_raw_tick_value = None
        self._num_rpi_counter_rollovers = 0
        self._pigpio_event_subscriber = None
        self._pigpio_connection = None

    def connect(self):
        if self._pigpio_connection is not None:
            self.stop()
        self._pigpio_connection = pigpio.pi(self.ip_address, self.pigpio_port)
        self._pigpio_connection.set_mode(self.gpio_pin_number, pigpio.INPUT)
        self._pigpio_connection.set_glitch_filter(
            self.gpio_pin_number, self.glitch_filter_us
        )

    def _pigpio_callback(self, pin_num, level, raw_ticks):
        if pin_num != self.gpio_pin_number:
            return

        self.sensor_pulse_event_handler_callback(
            self.get_timestamp_from_raw_ticks(raw_ticks), raw_ticks
        )

    def get_timestamp_from_raw_ticks(self, raw_ticks):
        if self._first_raw_tick_value is None:
            self._first_raw_tick_value = raw_ticks
        # The Raspberry Pi timer is a 32-bit unsigned counter that increments every microsecond, so
        # it rolls over every ~72 minutes. Here we keep track how many times the counter has rolled
        # over so we can adjust the raw tick count.
        if (
            self._last_raw_tick_value is not None
            and raw_ticks < self._last_raw_tick_value
        ):
            self._num_rpi_counter_rollovers += 1
        self._last_raw_tick_value = raw_ticks

        # Adjust the raw tick value so the first event happens at t=0 us; and also account for any
        # observed Raspberry Pi counter rollovers.
        adjusted_ticks = (
            raw_ticks
            - self._first_raw_tick_value
            + (self.RPI_TIMER_MAX_VALUE * self._num_rpi_counter_rollovers)
        )

        # Convert the adjusted tick count to seconds since the first tick
        return adjusted_ticks * self.RPI_TICK_PERIOD_IN_SECONDS

    def start(self, sensor_pulse_event_handler_callback):
        self.sensor_pulse_event_handler_callback = sensor_pulse_event_handler_callback
        self.connect()
        # The infrared sensor output goes low when a flywheel hole passes in front of it. This will
        # configure the pigpio callback thread so it calls our function whenever there's a falling
        # edge on our pin.
        self._pigpio_event_subscriber = self._pigpio_connection.callback(
            user_gpio=self.gpio_pin_number,
            edge=pigpio.FALLING_EDGE,
            func=self._pigpio_callback,
        )

    def stop(self):
        if self._pigpio_event_subscriber is not None:
            self._pigpio_event_subscriber.cancel()
        if self._pigpio_connection is not None:
            self._pigpio_connection.stop()
        self._first_raw_tick_value = None
        self._last_raw_tick_value = None
        self._num_rpi_counter_rollovers = 0
        self._pigpio_event_subscriber = None
        self._pigpio_connection = None


# Provides data from a pre-recorded workout. Useful for development and debugging.
class CsvFile(PiGpioClient):
    DUMMY_VALUE = 0

    def __init__(
        self,
        sensor_pulse_event_handler_callback,
        ticks_csv_file_path,
        raw_ticks_column_name="ticks",
        sample_delay=False
    ):
        self.sensor_pulse_event_handler_callback = sensor_pulse_event_handler_callback
        self.ticks_csv_file_path = ticks_csv_file_path
        self.raw_ticks_column_name = raw_ticks_column_name
        self._first_raw_tick_value = None
        self._last_raw_tick_value = None
        self._num_rpi_counter_rollovers = 0
        self.sample_delay = sample_delay
        self._reader_thread = None

    def start(self, sensor_pulse_event_handler_callback):
        self._reader_thread = CsvReaderThread(
            #file_path=self.ticks_csv_file_path,
            sensor_pulse_event_handler_callback=sensor_pulse_event_handler_callback,
            parent=self
        )
        # with open(self.ticks_csv_file_path) as input_file:
        #     csv_reader = csv.DictReader(input_file)
        #     for row in csv_reader:
        #         raw_ticks = int(row[self.raw_ticks_column_name])
        #         if raw_ticks == self.DUMMY_VALUE:
        #             continue
        #         sensor_pulse_event_handler_callback(
        #             self.get_timestamp_from_raw_ticks(raw_ticks),
        #             raw_ticks
        #         )
        #         if self.sample_delay:
        #             time.sleep(0.016)

    def stop(self):
        if self._reader_thread is not None:
            self._reader_thread.stop()


class CsvReaderThread(threading.Thread):
    def __init__(self, sensor_pulse_event_handler_callback, parent):
        threading.Thread.__init__(self)
        self.parent = parent
        self.input_file = open(self.parent.ticks_csv_file_path)
        self.csv_reader = csv.DictReader(self.input_file)
        self.sensor_pulse_event_handler_callback = sensor_pulse_event_handler_callback
        self.go = True
        self.start()

    def run(self):
        for row in self.csv_reader:
            if not self.go:
                break
            raw_ticks = int(row[self.parent.raw_ticks_column_name])
            if raw_ticks == self.parent.DUMMY_VALUE:
                continue
            self.sensor_pulse_event_handler_callback(
                self.parent.get_timestamp_from_raw_ticks(raw_ticks),
                raw_ticks
            )
            if self.parent.sample_delay:
                time.sleep(0.016)

    def stop(self):
        self.go = False
