import sys

from rower_monitor import config_loader as cf
from rower_monitor import data_sources as ds
from rower_monitor import workout as wo

import color_scales

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtChart import (
    QAreaSeries,
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QLineSeries,
    QValueAxis,
)

DEV_MODE = True


# Idea taken from: https://medium.com/@armin.samii/avoiding-random-crashes-when-multithreading-qt-f740dc16059
class SignalEmitter(QtCore.QObject):
    updated = QtCore.pyqtSignal()

    def __init__(self):
        super(SignalEmitter, self).__init__()


class RowingMonitorMainWindow(QtWidgets.QMainWindow):
    DISABLE_LOGGING = False

    COLOR_RED = QColor('#E03A3E')
    COLOR_BLUE = QColor('#009DDC')
    COLOR_DARK_GREY = QColor('#434343')
    COLOR_BLACK = QColor('#000000')

    PLOT_VISIBLE_SAMPLES = 200
    PLOT_MIN_Y = -1
    PLOT_MAX_Y = 55
    PLOT_TIME_WINDOW_SECONDS = 7
    PLOT_WIDTH_INCHES = 2
    PLOT_HEIGHT_INCHES = 1
    PLOT_DPI = 300
    PLOT_FAST_DRAWING = False

    WORK_PLOT_VISIBLE_STROKES = 64
    WORK_PLOT_MIN_Y = 0
    WORK_PLOT_MAX_Y = 350

    BOAT_SPEED_PLOT_VISIBLE_STROKES = 64
    BOAT_SPEED_PLOT_MIN_Y = 0
    BOAT_SPEED_PLOT_MAX_Y = 10

    GUI_FONT = QtGui.QFont('Nunito SemiBold', 12)
    GUI_FONT_LARGE = QtGui.QFont('Nunito', 24)
    GUI_FONT_MEDIUM = QtGui.QFont('Nunito', 16)

    def __init__(self, config, data_source, *args, **kwargs):
        super(RowingMonitorMainWindow, self).__init__(*args, **kwargs)

        self.setWindowTitle('Rowing Monitor')

        self.config = config
        self.log_folder_path = config.log_folder_path
        self.workout = wo.WorkoutMetricsTracker(
            config=config,
            data_source=data_source
        )

        # Connect workut emitter to UI update
        self.workout_qt_emitter = SignalEmitter()
        self.workout_qt_emitter.updated.connect(self.ui_callback)

        # Setup main window layout
        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        self.app_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.app_layout.setContentsMargins(0, 0, 0, 0) #(left, top, right, bottom)

        # Build button bar
        self.button_bar_background_widget = QtWidgets.QWidget(self.main_widget)
        self.button_bar_background_widget.setObjectName('ButtonBarBackground')
        self.button_bar_background_widget.setStyleSheet('QWidget#ButtonBarBackground {background-color: #F1F1F1;}')
        self.button_bar_layout = QtWidgets.QHBoxLayout(self.button_bar_background_widget)
        self.start_button = QtWidgets.QPushButton('Start')
        self.start_button.setFlat(True)

        # Start button style
        palette = self.start_button.palette()
        palette.setColor(palette.Button, self.COLOR_RED)
        palette.setColor(palette.ButtonText, QColor('white'))
        self.start_button.setAutoFillBackground(True)
        self.start_button.setPalette(palette)
        self.start_button.update()
        self.start_button.setFont(self.GUI_FONT)
        self.start_button.setMinimumSize(97, 60)
        self.start_button.setMaximumSize(97, 60)

        # Add to main window
        self.button_bar_layout.addWidget(self.start_button)
        #self.button_bar_layout.addWidget(self.button_bar_background_widget)
        self.button_bar_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.button_bar_layout.setContentsMargins(0, 0, 0, 0) #(left, top, right, bottom)
        self.app_layout.addWidget(self.button_bar_background_widget)#.addLayout(self.button_bar_layout)

        self.stats_layout = QtWidgets.QHBoxLayout()
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_layout.setSpacing(0)
        self.app_layout.addLayout(self.stats_layout)

        # Build workout stats bar
        self.metrics_panel_layout = QtWidgets.QVBoxLayout()
        self.charts_panel_layout = QtWidgets.QVBoxLayout()

        self.workout_totals_layout = QtWidgets.QVBoxLayout()
        self.time_label = QtWidgets.QLabel(self._format_total_workout_time(0))
        self.distance_label = QtWidgets.QLabel(self._format_total_workout_distance(0))
        self.time_label.setAlignment(QtCore.Qt.AlignCenter)
        self.distance_label.setAlignment(QtCore.Qt.AlignCenter)
        self.time_label.setFixedHeight(40)
        self.distance_label.setFixedHeight(30)
        self.workout_totals_layout.addWidget(self.time_label)
        self.workout_totals_layout.addWidget(self.distance_label)
        #self.workout_totals_layout.setSpacing(0)
        self.workout_totals_layout.setContentsMargins(0, 0, 0, 30)
        self.metrics_panel_layout.addLayout(self.workout_totals_layout)

        self.stroke_stats_layout = QtWidgets.QVBoxLayout()
        self.spm_label = QtWidgets.QLabel(self._format_strokes_per_minute(99))
        self.stroke_ratio_label = QtWidgets.QLabel(self._format_stroke_ratio(1))
        self.spm_label.setAlignment(QtCore.Qt.AlignCenter)
        self.stroke_ratio_label.setAlignment(QtCore.Qt.AlignCenter)
        self.spm_label.setFixedHeight(40)
        self.stroke_ratio_label.setFixedHeight(30)
        self.stroke_stats_layout.addWidget(self.spm_label)
        self.stroke_stats_layout.addWidget(self.stroke_ratio_label)
        #self.stroke_stats_layout.setSpacing(0)
        self.stroke_stats_layout.setContentsMargins(0, 30, 0, 30)
        self.metrics_panel_layout.addLayout(self.stroke_stats_layout)

        self.boat_stats_layout = QtWidgets.QVBoxLayout()
        self.boat_speed_label = QtWidgets.QLabel(self._format_boat_speed(0))
        self.split_time_label = QtWidgets.QLabel(self._format_boat_pace(0))
        self.boat_speed_label.setAlignment(QtCore.Qt.AlignCenter)
        self.split_time_label.setAlignment(QtCore.Qt.AlignCenter)
        self.boat_speed_label.setFixedHeight(40)
        self.split_time_label.setFixedHeight(30)
        self.boat_stats_layout.addWidget(self.boat_speed_label)
        self.boat_stats_layout.addWidget(self.split_time_label)
        #self.boat_stats_layout.setSpacing(0)
        self.boat_stats_layout.setContentsMargins(0, 30, 0, 0)
        self.metrics_panel_layout.addLayout(self.boat_stats_layout)

        # Appearance
        self.time_label.setFont(self.GUI_FONT_LARGE)
        self.distance_label.setFont(self.GUI_FONT_MEDIUM)
        self.spm_label.setFont(self.GUI_FONT_LARGE)
        self.stroke_ratio_label.setFont(self.GUI_FONT_MEDIUM)
        self.boat_speed_label.setFont(self.GUI_FONT_LARGE)
        self.split_time_label.setFont(self.GUI_FONT_MEDIUM)


        # Add to main window
        self.metrics_panel_layout.setSpacing(0)
        self.metrics_panel_layout.setContentsMargins(60, 30, 30, 30) #(left, top, right, bottom)
        self.charts_panel_layout.setSpacing(30)
        self.charts_panel_layout.setContentsMargins(30, 30, 60, 60)#(30, 30, 60, 60) #(left, top, right, bottom)
        self.stats_layout.addLayout(self.metrics_panel_layout)
        self.stats_layout.addLayout(self.charts_panel_layout)

        self.xdata = [0.0 for i in range(self.PLOT_VISIBLE_SAMPLES)]
        self.ydata = [0.0 for i in range(self.PLOT_VISIBLE_SAMPLES)]

        self.work_per_stroke_data = [0.0 for i in range(self.WORK_PLOT_VISIBLE_STROKES)]
        self.boat_speed_data = [0.0 for i in range(self.WORK_PLOT_VISIBLE_STROKES)]
        self.seen_strokes = 0

        ############################################
        # Add torque chart
        self.torque_plot = QChart()
        self.torque_plot.setContentsMargins(-26, -26, -26, -26)
        #self.torque_plot.setAnimationOptions(QChart.GridAxisAnimations)
        self.torque_plot.legend().setVisible(False)
        self.torque_plot_horizontal_axis = QValueAxis()
        self.torque_plot_vertical_axis = QValueAxis()
        self.torque_plot.addAxis(self.torque_plot_vertical_axis, QtCore.Qt.AlignLeft)
        self.torque_plot.addAxis(self.torque_plot_horizontal_axis, QtCore.Qt.AlignBottom)

        # Line series
        self.torque_plot_series = QLineSeries(self)
        for i in range(self.PLOT_VISIBLE_SAMPLES):
            self.torque_plot_series.append(0, 0)
        #self.torque_plot_series.setColor(QColor('#009DDC'))
        pen = self.torque_plot_series.pen()
        pen.setWidth(1)
        pen.setColor(self.COLOR_DARK_GREY)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        self.torque_plot_series.setPen(pen)

        # Area series
        self.torque_plot_area_series = QAreaSeries()
        self.torque_plot_area_series.setUpperSeries(self.torque_plot_series)
        self.torque_plot_area_series.setLowerSeries(QLineSeries(self))
        for i in range(self.PLOT_VISIBLE_SAMPLES):
            self.torque_plot_area_series.lowerSeries().append(0, 0)
        self.torque_plot_area_series.setColor(self.COLOR_DARK_GREY)
        self.torque_plot_area_series.setBorderColor(self.COLOR_DARK_GREY)

        # Compose plot
        self.torque_plot.addSeries(self.torque_plot_area_series)
        self.torque_plot_area_series.attachAxis(self.torque_plot_horizontal_axis)
        self.torque_plot_area_series.attachAxis(self.torque_plot_vertical_axis)
        self.torque_plot.addSeries(self.torque_plot_series)
        self.torque_plot_series.attachAxis(self.torque_plot_horizontal_axis)
        self.torque_plot_series.attachAxis(self.torque_plot_vertical_axis)

        # Set axes range
        self.torque_plot_vertical_axis.setRange(self.PLOT_MIN_Y, self.PLOT_MAX_Y)
        #self.torque_plot_vertical_axis.setTickCount(10)
        self.torque_plot_vertical_axis.setVisible(False)
        self.torque_plot_horizontal_axis.setRange(-self.PLOT_TIME_WINDOW_SECONDS, 0)
        self.torque_plot_horizontal_axis.setVisible(False)

        # Add plot view to GUI
        self.torque_plot_chartview = QChartView(self.torque_plot)
        self.torque_plot_chartview.setRenderHint(QPainter.Antialiasing)
        #self.torque_plot_chartview.setMinimumHeight(250)
        #self.torque_plot_chartview.resize(250, 250)

        self.torque_plot_box = QtWidgets.QGroupBox("Force")
        self.torque_plot_box.setFont(self.GUI_FONT)
        self.torque_plot_box.setAlignment(QtCore.Qt.AlignLeft)
        self.torque_plot_box_layout = QtWidgets.QVBoxLayout()
        self.torque_plot_box_layout.addWidget(self.torque_plot_chartview)
        self.torque_plot_box.setLayout(self.torque_plot_box_layout)

        self.charts_panel_layout.addWidget(self.torque_plot_box)
        ############################################

        ############################################
        # Add work chart
        self.work_plot = QChart()
        self.work_plot.setContentsMargins(-26, -26, -26, -26)
        self.work_plot.legend().setVisible(False)
        self.work_plot_horizontal_axis = QBarCategoryAxis()
        self.work_plot_vertical_axis = QValueAxis()
        self.work_plot.addAxis(self.work_plot_vertical_axis, QtCore.Qt.AlignLeft)
        self.work_plot.addAxis(self.work_plot_horizontal_axis, QtCore.Qt.AlignBottom)

        # Define series
        self.work_plot_series = QBarSeries()
        self.work_plot_bar_set_list = [QBarSet(str(i)) for i in range(self.WORK_PLOT_VISIBLE_STROKES)]
        self.work_plot_series.append(self.work_plot_bar_set_list)
        for bar_set in self.work_plot_bar_set_list:
            bar_set.append(0)
        self.work_plot_series.setBarWidth(1.0)

        # Compose plot
        self.work_plot.addSeries(self.work_plot_series)
        self.work_plot_series.attachAxis(self.work_plot_horizontal_axis)
        self.work_plot_series.attachAxis(self.work_plot_vertical_axis)

        # Set axes range
        self.work_plot_vertical_axis.setRange(self.WORK_PLOT_MIN_Y, self.WORK_PLOT_MAX_Y)
        self.work_plot_vertical_axis.setTickCount(8)
        self.work_plot_vertical_axis.setVisible(False)
        self.work_plot_horizontal_axis.append("1")
        self.work_plot_horizontal_axis.setVisible(False)

        # Add plot view to GUI
        self.work_plot_chartview = QChartView(self.work_plot)
        self.work_plot_chartview.setRenderHint(QPainter.Antialiasing)
        #self.work_plot_chartview.setMinimumHeight(250)
        #self.work_plot_chartview.resize(250, 250)

        self.work_plot_box = QtWidgets.QGroupBox("Work per stroke")
        self.work_plot_box.setFont(self.GUI_FONT)

        self.work_plot_box.setAlignment(QtCore.Qt.AlignLeft)
        self.work_plot_box_layout = QtWidgets.QVBoxLayout()
        self.work_plot_box_layout.addWidget(self.work_plot_chartview)
        self.work_plot_box.setLayout(self.work_plot_box_layout)

        self.charts_panel_layout.addWidget(self.work_plot_box)
        ############################################

        ############################################
        # Add boat speed chart
        self.boat_speed_plot = QChart()
        self.boat_speed_plot.setContentsMargins(-26, -26, -26, -26)
        #self.boat_speed_plot.setBackgroundRoundness(0)
        self.boat_speed_plot.legend().setVisible(False)
        self.boat_speed_plot_horizontal_axis = QBarCategoryAxis()
        self.boat_speed_plot_vertical_axis = QValueAxis()
        self.boat_speed_plot.addAxis(self.boat_speed_plot_vertical_axis, QtCore.Qt.AlignLeft)
        self.boat_speed_plot.addAxis(self.boat_speed_plot_horizontal_axis, QtCore.Qt.AlignBottom)

        # Define series
        self.boat_speed_plot_series = QBarSeries()
        self.boat_speed_plot_bar_set_list = [QBarSet(str(i)) for i in range(self.BOAT_SPEED_PLOT_VISIBLE_STROKES)]
        self.boat_speed_plot_series.append(self.boat_speed_plot_bar_set_list)
        for bar_set in self.boat_speed_plot_bar_set_list:
            bar_set.append(0)
        self.boat_speed_plot_series.setBarWidth(1.0)

        # Compose plot
        self.boat_speed_plot.addSeries(self.boat_speed_plot_series)
        self.boat_speed_plot_series.attachAxis(self.boat_speed_plot_horizontal_axis)
        self.boat_speed_plot_series.attachAxis(self.boat_speed_plot_vertical_axis)

        # Set axes range
        self.boat_speed_plot_vertical_axis.setRange(self.BOAT_SPEED_PLOT_MIN_Y, self.BOAT_SPEED_PLOT_MAX_Y)
        self.boat_speed_plot_vertical_axis.setTickCount(8)
        self.boat_speed_plot_vertical_axis.setVisible(False)
        self.boat_speed_plot_horizontal_axis.append("1")
        self.boat_speed_plot_horizontal_axis.setVisible(False)

        # Add plot view to GUI
        self.boat_speed_plot_chartview = QChartView(self.boat_speed_plot)
        self.boat_speed_plot_chartview.setRenderHint(QPainter.Antialiasing)
        #self.boat_speed_plot_chartview.setContentsMargins(0, 0, 0, 0)
        self.boat_speed_plot_box = QtWidgets.QGroupBox("Boat speed")
        self.boat_speed_plot_box.setFont(self.GUI_FONT)
        #self.boat_speed_plot_box.setFlat(True)
        #self.boat_speed_plot_box.setContentsMargins(0, 0, 0, 0)
        #self.boat_speed_plot_box.setObjectName("BoatSpeedGB")  # Changed here...
        #self.boat_speed_plot_box.setStyleSheet('QGroupBox {background-color: white;}')
        #self.main_widget.setStyleSheet('QGroupBox::title { background-color: blue }')

        self.boat_speed_plot_box.setAlignment(QtCore.Qt.AlignLeft)
        self.boat_speed_plot_box_layout = QtWidgets.QVBoxLayout()
        self.boat_speed_plot_box_layout.addWidget(self.boat_speed_plot_chartview)
        self.boat_speed_plot_box.setLayout(self.boat_speed_plot_box_layout)

        self.charts_panel_layout.addWidget(self.boat_speed_plot_box)


        ############################################

        # Set interaction behavior
        self.start_button.clicked.connect(self.start)

        # Update workout duration every second
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.timer_tick)

        self.start_timestamp = None
        self.started = False

        self.show()

    def update_torque_plot(self):
        self.torque_plot_series.append(self.xdata[-1], self.ydata[-1])
        self.torque_plot_series.remove(0)
        self.torque_plot_area_series.lowerSeries().append(self.xdata[-1], 0)
        self.torque_plot_area_series.lowerSeries().remove(0)
        self.torque_plot_horizontal_axis.setRange(self.xdata[-1] - self.PLOT_TIME_WINDOW_SECONDS, self.xdata[-1])

    def update_work_plot(self):
        # Create new bar set
        new_bar_set = QBarSet(str(self.seen_strokes))
        value = self.work_per_stroke_data[-1]
        new_bar_set.append(value)
        new_bar_set.setColor(
            color_scales.viridis.get_color_from_normalized_value(value / self.WORK_PLOT_MAX_Y)
        )
        # Append new set, and remove oldest
        self.work_plot_series.append(new_bar_set)
        self.work_plot_series.remove(self.work_plot_series.barSets()[0])

    def update_boat_speed_plot(self):
        # Create new bar set
        new_bar_set = QBarSet(str(self.seen_strokes))
        value = self.boat_speed_data[-1]
        new_bar_set.append(value)
        new_bar_set.setColor(
            color_scales.plasma.get_color_from_normalized_value(value / self.BOAT_SPEED_PLOT_MAX_Y)
        )
        # Append new set, and remove oldest
        self.boat_speed_plot_series.append(new_bar_set)
        self.boat_speed_plot_series.remove(self.boat_speed_plot_series.barSets()[0])

    def start(self):
        if not self.started:
            self.start_workout()
            self.start_button.setText('Stop')
            self.started = True
        else:
            self.stop_workout()
            self.start_button.setText('Start')
            self.started = False

    def start_workout(self):
        self.timer.start()
        self.workout.start(qt_signal_emitter=self.workout_qt_emitter)

    def stop_workout(self):
        self.timer.stop()
        self.workout.stop()
        if not self.DISABLE_LOGGING and not DEV_MODE:
            self.workout.save(output_folder_path=self.log_folder_path)

    def _format_total_workout_time(self, value_seconds):
        minutes = value_seconds // 60
        seconds = value_seconds % 60
        return '%d:%02d' % (minutes, seconds)

    def _format_total_workout_distance(self, value):
        return f'{int(value):,} m'

    def _format_strokes_per_minute(self, value):
        return '%.1f spm' % value

    def _format_stroke_ratio(self, value):
        return '1:%.1f ratio' % value

    def _format_boat_speed(self, value):
        return '%0.2f m/s' % value

    def _format_boat_pace(self, value_seconds):
        return '%s /500m' % (self._format_total_workout_time(value_seconds))

    def ui_callback(self):
        # If this is the first pulse, capture the current time
        if self.start_timestamp is None:
            self.start_timestamp = QtCore.QTime.currentTime()
        # Update distance
        distance = self.workout.boat.position.values[-1]
        self.distance_label.setText(self._format_total_workout_distance(distance))
        if len(self.workout.person.torque) > 0:
            self.ydata = self.ydata[1:] + [self.workout.person.torque.values[-1]]
            self.xdata = self.xdata[1:] + [self.workout.person.torque.timestamps[-1]]
            self.update_torque_plot()
        # Update SPM
        new_stroke_info_available = len(self.workout.person.strokes) > self.seen_strokes
        if new_stroke_info_available:
            # SPM indicator
            spm = 60 / self.workout.person.strokes.values[-1].duration
            ratio = self.workout.person.strokes.values[-1].drive_to_recovery_ratio
            self.spm_label.setText(self._format_strokes_per_minute(spm))
            self.stroke_ratio_label.setText(self._format_stroke_ratio(ratio))
            # Work plot
            self.work_per_stroke_data = self.work_per_stroke_data[1:] + \
                                        [self.workout.person.strokes.values[-1].work_done_by_person]
            self.update_work_plot()
            self.seen_strokes += 1
            # Boat speed plot
            average_boat_speed = self.workout.boat.speed.get_average_value(
                start_time=self.workout.person.strokes.values[-1].start_time,
                end_time=self.workout.person.strokes.values[-1].end_time
            )
            self.boat_speed_data = self.boat_speed_data[1:] + [average_boat_speed]
            self.boat_speed_label.setText(self._format_boat_speed(average_boat_speed))
            split_time_seconds = 500.0 / average_boat_speed
            self.split_time_label.setText(self._format_boat_pace(split_time_seconds))
            self.update_boat_speed_plot()

    def timer_tick(self):
        # Do nothing if we haven't received an encoder pulse yet.
        if self.start_timestamp is None:
            return
        # Update workout time label
        time_since_start = self.start_timestamp.secsTo(QtCore.QTime.currentTime())
        self.time_label.setText(self._format_total_workout_time(time_since_start))


app_config = cf.load_config()
if DEV_MODE:
    app_data_source = ds.CsvFile(
        "C:\\Users\\checo\\Desktop\\rower\\2020-08-28 22h49m22s.csv",
        sample_delay=True,
        threaded=True
    )
else:
    app_data_source = ds.PiGpioClient(
        ip_address=app_config.ip_address,
        pigpio_port=app_config.pigpio_daemon_port,
        gpio_pin_number=app_config.gpio_pin_numer
    )
print('Connected!')
app = QtWidgets.QApplication(sys.argv)
pal = app.palette()
pal.setColor(QtGui.QPalette.Window, QtCore.Qt.white)
app.setPalette(pal)

w = RowingMonitorMainWindow(app_config, app_data_source)
w.resize(700, 700)
app.exec_()
