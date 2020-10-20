class TimeSeries:
    def __init__(self, values=None, timestamps=None):
        if values is None:
            values = []
        if timestamps is None:
            timestamps = []
        self.values = values
        self.timestamps = timestamps

    def append(self, value, timestamp):
        self.values.append(value)
        self.timestamps.append(timestamp)

    def get_time_slice(self, start_time, end_time):
        """Returns a time series of all samples within the time interval [start_time, end_time] (inclusive)."""
        included_mask = [start_time <= i <= end_time for i in self.timestamps]
        try:
            first_included_item_idx = included_mask.index(True)
        except ValueError:
            # Included mask is all-false, return empty time series.
            return TimeSeries()
        else:
            last_included_item_idx = len(included_mask) - included_mask[::-1].index(True)
            return self[first_included_item_idx: last_included_item_idx]

    def get_average_value(self, start_time=None, end_time=None):
        if start_time is None and end_time is None:
            data = self
        else:
            data = self.get_time_slice(start_time, end_time)
        total_time = data.timestamps[-1] - data.timestamps[0]
        accum = 0.0
        for idx, (value, timestamp) in enumerate(data):
            if idx == len(data) - 1:
                duration = 0
            else:
                next_timestamp = data.timestamps[idx+1]
                duration = next_timestamp - timestamp  # TODO: is this the right way to calculate this?
            accum += value * duration
        return accum / total_time

    def interpolate_midpoints(self):
        """Returns interpolated samples at the midpoints of the existing data points. We use this to align the
        timestamps of acceleration and speed time series."""
        # TODO: Fancy polynomial interpolation
        result = TimeSeries()
        for idx, (value, timestamp) in enumerate(self):
            if idx == len(self) - 1:
                break
            next_value_in_ts, next_timestamp_in_ts = self[idx + 1]
            result.append(
                value=(value + next_value_in_ts) / 2.0,
                timestamp=(timestamp + next_timestamp_in_ts) / 2.0
            )
        return result

    def __getitem__(self, idx):
        if type(idx) is int:
            return self.values[idx], self.timestamps[idx]
        elif type(idx) is slice:
            return TimeSeries(values=self.values[idx], timestamps=self.timestamps[idx])
        else:
            raise IndexError()

    def __len__(self):
        return len(self.values)

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return repr(self.__dict__)
