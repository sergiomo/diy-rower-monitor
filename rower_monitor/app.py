import sys

import data_sources as ds
import workout as wo

from threading import Lock
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtChart import (
    QChart,
    QChartView,
    QLineSeries,
    QValueAxis,
    QAreaSeries,
    QBarSeries,
    QBarSet,
    QBarCategoryAxis,
)


# Idea taken from: https://medium.com/@armin.samii/avoiding-random-crashes-when-multithreading-qt-f740dc16059
class SignalEmitter(QtCore.QObject):
    updated = QtCore.pyqtSignal()

    def __init__(self):
        super(SignalEmitter, self).__init__()


class RowingMonitorMainWindow(QtWidgets.QMainWindow):

    DEV_MODE = True

    LOG_FOLDER_PATH = 'C:\\Users\\checo\\Dropbox\\rower\\logs'

    PLOT_VISIBLE_SAMPLES = 200
    PLOT_MIN_Y = -10
    PLOT_MAX_Y = 55
    PLOT_TIME_WINDOW_SECONDS = 7
    PLOT_WIDTH_INCHES = 2
    PLOT_HEIGHT_INCHES = 1
    PLOT_DPI = 300
    PLOT_FAST_DRAWING = False

    WORK_PLOT_VISIBLE_STROKES = 10
    WORK_PLOT_MIN_Y = 0
    WORK_PLOT_MAX_Y = 350

    GUI_FONT = QtGui.QFont('Nunito', 10)
    GUI_FONT_LARGE = QtGui.QFont('Nunito', 24)
    GUI_FONT_MEDIUM = QtGui.QFont('Nunito', 16)

    def __init__(self, data_source, *args, **kwargs):
        super(RowingMonitorMainWindow, self).__init__(*args, **kwargs)

        self.redraw_lock = Lock()
        self.workout = wo.WorkoutMetricsTracker(data_source)

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
        self.button_bar_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton('Start')
        #self.stop_button.setStyleSheet(
        #    'background-color: #E03A3E; border: none; color: #ffffff'
        #)
        # Appearance
        self.start_button.setFont(self.GUI_FONT)
        self.start_button.setMinimumSize(97, 60)
        self.start_button.setMaximumSize(97, 60)
        # Add to main window
        self.button_bar_layout.addWidget(self.start_button)
        self.button_bar_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.button_bar_layout.setContentsMargins(0, 0, 0, 0) #(left, top, right, bottom)
        self.app_layout.addLayout(self.button_bar_layout)

        self.stats_layout = QtWidgets.QHBoxLayout()
        self.app_layout.addLayout(self.stats_layout)

        # Build workout stats bar
        self.metrics_panel_layout = QtWidgets.QVBoxLayout()
        self.charts_panel_layout = QtWidgets.QVBoxLayout()
        self.metrics_panel_layout.setContentsMargins(60, 10, 60, 60) #(left, top, right, bottom)
        self.charts_panel_layout.setContentsMargins(0, 10, 60, 60) #(left, top, right, bottom)

        self.workout_totals_layout = QtWidgets.QVBoxLayout()
        self.time_label = QtWidgets.QLabel('0:00')
        self.distance_label = QtWidgets.QLabel('0 m')
        self.time_label.setAlignment(QtCore.Qt.AlignCenter)
        self.distance_label.setAlignment(QtCore.Qt.AlignCenter)
        self.time_label.setFixedHeight(40)
        self.distance_label.setFixedHeight(30)
        self.workout_totals_layout.addWidget(self.time_label)
        self.workout_totals_layout.addWidget(self.distance_label)
        self.workout_totals_layout.setSpacing(0)
        self.metrics_panel_layout.addLayout(self.workout_totals_layout)

        self.stroke_stats_layout = QtWidgets.QVBoxLayout()
        self.spm_label = QtWidgets.QLabel('0.00 spm')
        self.stroke_ratio_label = QtWidgets.QLabel('1:1 ratio')
        self.spm_label.setAlignment(QtCore.Qt.AlignCenter)
        self.stroke_ratio_label.setAlignment(QtCore.Qt.AlignCenter)
        self.spm_label.setFixedHeight(40)
        self.stroke_ratio_label.setFixedHeight(30)
        self.stroke_stats_layout.addWidget(self.spm_label)
        self.stroke_stats_layout.addWidget(self.stroke_ratio_label)
        self.stroke_stats_layout.setSpacing(0)
        self.metrics_panel_layout.addLayout(self.stroke_stats_layout)

        self.boat_stats_layout = QtWidgets.QVBoxLayout()
        self.boat_speed_label = QtWidgets.QLabel('0.00 m/s')
        self.split_time_label = QtWidgets.QLabel('0:00 /500m')
        self.boat_speed_label.setAlignment(QtCore.Qt.AlignCenter)
        self.split_time_label.setAlignment(QtCore.Qt.AlignCenter)
        self.boat_speed_label.setFixedHeight(40)
        self.split_time_label.setFixedHeight(30)
        self.boat_stats_layout.addWidget(self.boat_speed_label)
        self.boat_stats_layout.addWidget(self.split_time_label)
        self.boat_stats_layout.setSpacing(0)
        self.boat_stats_layout.setContentsMargins(0, 0, 0, 0)
        #self.boat_stats_layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        #self.boat_stats_layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
        self.metrics_panel_layout.addLayout(self.boat_stats_layout)

        # Appearance
        self.time_label.setFont(self.GUI_FONT_LARGE)
        self.distance_label.setFont(self.GUI_FONT_MEDIUM)
        self.spm_label.setFont(self.GUI_FONT_LARGE)
        self.stroke_ratio_label.setFont(self.GUI_FONT_MEDIUM)
        self.boat_speed_label.setFont(self.GUI_FONT_LARGE)
        self.split_time_label.setFont(self.GUI_FONT_MEDIUM)


        # Add to main window
        self.metrics_panel_layout.setSpacing(30)
        self.metrics_panel_layout.setContentsMargins(30, 0, 30, 0) #(left, top, right, bottom)
        self.stats_layout.addLayout(self.metrics_panel_layout)
        self.stats_layout.addLayout(self.charts_panel_layout)

        self.xdata = [0.0 for i in range(self.PLOT_VISIBLE_SAMPLES)]
        self.ydata = [0.0 for i in range(self.PLOT_VISIBLE_SAMPLES)]

        self.work_per_stroke_data = [0.0 for i in range(self.WORK_PLOT_VISIBLE_STROKES)]
        self.seen_strokes = 0

        # Add torque chart
        ############################################
        # Axes
        self.torque_plot = QChart()
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
        self.torque_plot_series.setColor(QColor('red'))

        # Area series
        self.torque_plot_area_series = QAreaSeries()
        self.torque_plot_area_series.setUpperSeries(self.torque_plot_series)
        self.torque_plot_area_series.setLowerSeries(QLineSeries(self))
        for i in range(self.PLOT_VISIBLE_SAMPLES):
            self.torque_plot_area_series.lowerSeries().append(0, 0)
        self.torque_plot_area_series.setColor(QColor('blue'))

        # Compose plot
        self.torque_plot.addSeries(self.torque_plot_area_series)
        self.torque_plot_area_series.attachAxis(self.torque_plot_horizontal_axis)
        self.torque_plot_area_series.attachAxis(self.torque_plot_vertical_axis)
        self.torque_plot.addSeries(self.torque_plot_series)
        self.torque_plot_series.attachAxis(self.torque_plot_horizontal_axis)
        self.torque_plot_series.attachAxis(self.torque_plot_vertical_axis)

        # Set axes range
        self.torque_plot_vertical_axis.setRange(self.PLOT_MIN_Y, self.PLOT_MAX_Y)
        self.torque_plot_vertical_axis.setTickCount(2)
        self.torque_plot_vertical_axis.setVisible(False)
        self.torque_plot_horizontal_axis.setRange(-8, 0)
        self.torque_plot_horizontal_axis.setVisible(False)
        self.torque_plot_vertical_axis.setTickCount(10)

        # Add plot view to GUI
        self.torque_plot_chartview = QChartView(self.torque_plot)
        self.torque_plot_chartview.setRenderHint(QPainter.Antialiasing)
        self.torque_plot_chartview.setMinimumHeight(250)
        self.torque_plot_chartview.resize(250, 250)
        self.charts_panel_layout.addWidget(self.torque_plot_chartview)
        ############################################

        ############################################
        # Add work chart
        self.work_plot = QChart()
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
        self.work_plot_vertical_axis.setVisible(True)
        self.work_plot_horizontal_axis.append("1")
        self.work_plot_horizontal_axis.setVisible(False)

        # Add plot view to GUI
        self.work_plot_chartview = QChartView(self.work_plot)
        self.work_plot_chartview.setRenderHint(QPainter.Antialiasing)
        self.work_plot_chartview.setMinimumHeight(250)
        self.work_plot_chartview.resize(250, 250)
        self.charts_panel_layout.addWidget(self.work_plot_chartview)
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
        value_rel = int(value * 255 / self.WORK_PLOT_MAX_Y)
        new_bar_set.append(value)
        new_bar_set.setColor(QColor(value_rel, value_rel, value_rel))
        # Append new set, and remove oldest
        self.work_plot_series.append(new_bar_set)
        self.work_plot_series.remove(self.work_plot_series.barSets()[0])

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
        if not self.DEV_MODE:
            self.workout.save(output_folder_path=self.LOG_FOLDER_PATH)

    def ui_callback(self):
        # If this is the first pulse, capture the current time
        if self.start_timestamp is None:
            self.start_timestamp = QtCore.QTime.currentTime()
        # Update distance
        distance = self.workout.num_flywheel_revolutions
        self.distance_label.setText('%d m' % distance)
        if len(self.workout.torque) > 0:
            self.ydata = self.ydata[1:] + [self.workout.torque.values[-1]]
            self.xdata = self.xdata[1:] + [self.workout.torque.timestamps[-1]]
            self.update_torque_plot()
        # Update SPM
        new_stroke_info_available = len(self.workout.strokes) > self.seen_strokes
        if new_stroke_info_available:
            # SPM indicator
            spm = 60 / self.workout.strokes.values[-1].duration
            ratio = self.workout.strokes.values[-1].recovery_to_drive_ratio
            self.spm_label.setText('%.1f spm' % spm)
            self.stroke_ratio_label.setText('%.1f:1 ratio' % ratio)
            # Work plot
            self.work_per_stroke_data = self.work_per_stroke_data[1:] + [self.workout.strokes.values[-1].work_done_by_person]
            self.update_work_plot()
            self.seen_strokes += 1

    def timer_tick(self):
        # Do nothing if we haven't received an encoder pulse yet.
        if self.start_timestamp is None:
            return
        # Update workout time label
        time_since_start = self.start_timestamp.secsTo(QtCore.QTime.currentTime())
        minutes = time_since_start // 60
        seconds = time_since_start % 60
        time_string = '%d:%02d' % (minutes, seconds)
        self.time_label.setText(time_string)


data_source = ds.CsvFile(
    "C:\\Users\\checo\\Desktop\\rower\\2020-08-28 22h49m22s.csv",
    sample_delay=True,
    threaded=True
)

#data_source = ds.PiGpioClient(ip_address='192.168.1.218', pigpio_port=9876, gpio_pin_number=17)
print('Connected!')
app = QtWidgets.QApplication(sys.argv)
w = RowingMonitorMainWindow(data_source)
w.resize(900, 600)
app.exec_()
