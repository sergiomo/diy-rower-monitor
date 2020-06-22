import csv
import pigpio

class DataSource:
    def __init__(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass

class PiGpioClient(DataSource):
    #The maximum number of ticks that the Raspberry Pi can count up to before rolling over.
    #Constant taken from https://github.com/joan2937/pigpio/blob/v76/pigpio.py#L961
    RPI_TIMER_MAX_VALUE = 1 << 32
    RPI_TICK_PERIOD_IN_SECONDS = 1e-6
    RPI_IP_ADDRESS = '192.168.1.242'
    RPI_PIGPIO_PORT = 9876
    RPI_PIN_NUMBER = 17

    #The reflective infrared sensor does not have hysteresis, so we need to filter out glitches in
    #software.
    GLITCH_FILTER_US = 1000

    def __init__(self,
                 rising_edge_event_handler_callback,
                 ip_address=self.RPI_IP_ADDRESS,
                 pigpio_port=self.RPI_PIGPIO_PORT,
                 gpio_pin_number=self.RPI_PIN_NUMBER,
                 glitch_filter_us=self.GLITCH_FILTER_US):
        self.rising_edge_event_handler_callback = rising_edge_event_handler_callback
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
        self._pigpio_connection.set_glitch_filter(self.gpio_pin_number, self.glitch_filter_us)

    def _pigpio_callback(self, pin_num, level, raw_ticks):
        if pin_num != self.gpio_pin_number:
            return
        
        self.rising_edge_event_handler_callback(
            self.get_timestamp_from_raw_ticks(raw_ticks),
            raw_ticks
        )

    def get_timestamp_from_raw_ticks(self, raw_ticks):
        if self._first_raw_tick_value is None:
            self._first_raw_tick_value = raw_ticks
        #The Raspberry Pi timer is a 32-bit unsigned counter that increments every microsecond, so
        #it rolls over every ~72 minutes. Here we keep track how many times the counter has rolled
        #over so we can adjust the raw tick count.
        if self._last_raw_tick_value is not None and raw_ticks < self._last_raw_tick_value:
            self._num_rpi_counter_rollovers += 1
        self._last_raw_tick_value = raw_ticks
        
        #Adjust the raw tick value so the first event happens at t=0 us; and also account for any
        #observed Raspberry Pi counter rollovers.
        adjusted_ticks = ticks - self._first_observed_raw_tick_value + (
            self.RPI_TIMER_MAX_VALUE * self._num_rpi_counter_rollovers
        )

        #Convert the adjusted tick count to seconds since the first tick
        return adjusted_ticks * self.RPI_TICK_PERIOD_IN_SECONDS
        

    def start(self):
        self.connect()
        #This will configure the pigpio callback thread so it calls our function whenever there's a
        #rising edge on our pin.
        self._pigpio_event_subscriber = self._pigpio_connection.callback(
            user_gpio=self.gpio_pin_number,
            edge=pigpio.RISING_EDGE,
            func=self._pigpio_callback
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


#Provides data from a pre-recorded workout. Useful for development and debugging.
class CsvFile(DataSource):
    DUMMY_VALUE = 0
    
    def __init__(self,
                 rising_edge_event_handler_callback,
                 ticks_csv_file_path,
                 ticks_column_name='ticks'):
        self.rising_edge_event_handler_callback = rising_edge_event_handler_callback
        self.ticks_csv_file_path = ticks_csv_file_path
        self.ticks_column_name = ticks_column_name

    def start(self):
        with open(self.ticks_csv_file_path) as input_file:
            csv_reader = csv.DictReader(input_file)
            for row in csv_reader:
                tick = int(row[self.ticks_column_name])
                if tick == self.DUMMY_VALUE:
                    continue
                self.rising_edge_event_handler_callback(
                    tick
                    raw_ticks,
                )

    def stop(self):
        pass


