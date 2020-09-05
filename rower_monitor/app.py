import sys
import matplotlib

import data_sources as ds
import workout as wo

from threading import Lock
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis, QAreaSeries

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

matplotlib.use('Qt5Agg')


# Idea taken from: https://medium.com/@armin.samii/avoiding-random-crashes-when-multithreading-qt-f740dc16059
class SignalEmitter(QtCore.QObject):
    updated = QtCore.pyqtSignal()

    def __init__(self):
        super(SignalEmitter, self).__init__()


class MplCanvas(FigureCanvas):
    PLOT_MIN_Y = -10
    PLOT_MAX_Y = 55

    def __init__(self, width, height, dpi):
        fig = Figure(
            figsize=(width, height),
            dpi=dpi,
            facecolor='#2c2c2c',
            frameon=True,
            tight_layout=False,
        )
        self.axes = fig.add_axes([0,0,1,1], frameon=False)
        self.axes.get_xaxis().set_visible(False)
        self.axes.get_yaxis().set_visible(False)
        self.axes.set_ylim(self.PLOT_MIN_Y, self.PLOT_MAX_Y)
        super(MplCanvas, self).__init__(fig)


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

    GUI_FONT = QtGui.QFont('Roboto Mono', 10)

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
        self.app_layout.setContentsMargins(60, 60, 60, 60) #(left, top, right, bottom)

        # Build button bar
        self.button_bar_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton('Start')
        self.stop_button = QtWidgets.QPushButton('Stop')
        #self.stop_button.setStyleSheet(
        #    'background-color: #E03A3E; border: none; color: #ffffff'
        #)
        # Appearance
        self.start_button.setFont(self.GUI_FONT)
        self.stop_button.setFont(self.GUI_FONT)
        # Add to main window
        self.button_bar_layout.addWidget(self.start_button)
        self.button_bar_layout.addWidget(self.stop_button)
        self.button_bar_layout.setContentsMargins(0, 0, 0, 30)
        self.app_layout.addLayout(self.button_bar_layout)

        # Build workout stats bar
        self.stats_bar_layout = QtWidgets.QHBoxLayout()
        self.workout_label = QtWidgets.QLabel('Workout')
        self.time_label = QtWidgets.QLabel('0:00')
        self.distance_label = QtWidgets.QLabel('0 revs')
        # Appearance
        self.workout_label.setFont(self.GUI_FONT)
        self.time_label.setFont(self.GUI_FONT)
        self.distance_label.setFont(self.GUI_FONT)
        self.workout_label.setAlignment(QtCore.Qt.AlignCenter)
        self.time_label.setAlignment(QtCore.Qt.AlignCenter)
        self.distance_label.setAlignment(QtCore.Qt.AlignCenter)
        # Add to main window
        self.stats_bar_layout.addWidget(self.workout_label)
        self.stats_bar_layout.addWidget(self.time_label)
        self.stats_bar_layout.addWidget(self.distance_label)
        self.stats_bar_layout.setContentsMargins(0, 0, 0, 30)
        self.app_layout.addLayout(self.stats_bar_layout)

        # Add chart
        self.torque_plot_box = QtWidgets.QGroupBox('Torque')
        self.torque_plot_box.setAlignment(QtCore.Qt.AlignHCenter)
        self.torque_plot_box.setFont(self.GUI_FONT)
        self.canvas = MplCanvas(width=self.PLOT_WIDTH_INCHES,
                                height=self.PLOT_HEIGHT_INCHES,
                                dpi=self.PLOT_DPI)
        self.torque_plot_box_layout = QtWidgets.QVBoxLayout()
        self.torque_plot_box_layout.addWidget(self.canvas)
        self.torque_plot_box.setLayout(self.torque_plot_box_layout)
        self.app_layout.addWidget(self.torque_plot_box)
        # Initialize chart, and set things up for fast drawing.
        self.xdata = [None for i in range(self.PLOT_VISIBLE_SAMPLES)]
        self.ydata = [None for i in range(self.PLOT_VISIBLE_SAMPLES)]
        self.torque_plot, self.old_size = self.init_plot()




        ############################################
        self.torque_plot_2_series = QLineSeries(self)
        for i in range(self.PLOT_VISIBLE_SAMPLES):
            self.torque_plot_2_series.append(0, 0)

        self.torque_plot_2_series.setColor(QColor('blue'))

        self.tp2_horizontal_axis = QValueAxis()
        self.tp2_vertical_axis = QValueAxis()

        self.torque_plot_2 = QChart()

        self.torque_plot_2.addSeries(self.torque_plot_2_series)
        self.torque_plot_2.addAxis(self.tp2_vertical_axis, QtCore.Qt.AlignLeft)
        self.torque_plot_2.addAxis(self.tp2_horizontal_axis, QtCore.Qt.AlignBottom)

        self.torque_plot_2_series.attachAxis(self.tp2_horizontal_axis)
        self.torque_plot_2_series.attachAxis(self.tp2_vertical_axis)

        self.tp2_vertical_axis.setRange(self.PLOT_MIN_Y, self.PLOT_MAX_Y)
        self.tp2_vertical_axis.setTickCount(1)
        self.tp2_vertical_axis.setVisible(False)
        self.tp2_horizontal_axis.setRange(-8, 0)
        self.tp2_horizontal_axis.setVisible(False)
        self.tp2_vertical_axis.setTickCount(10)



        #self.torque_plot_2.setAnimationOptions(QChart.GridAxisAnimations)
        self.torque_plot_2.legend().setVisible(False)
        chartview = QChartView(self.torque_plot_2)
        chartview.setRenderHint(QPainter.Antialiasing)
        chartview.setMinimumHeight(250)
        chartview.resize(250, 250)
        self.app_layout.addWidget(chartview)
        ############################################

        # Set interaction behavior
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)

        # Update workout duration every second
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.timer_tick)

        self.start_timestamp = None
        self.started = False

        self.show()

    def update_plot_2(self):
        self.torque_plot_2_series.append(self.xdata[-1], self.ydata[-1])
        self.torque_plot_2_series.remove(0)
        self.tp2_horizontal_axis.setRange(self.xdata[-1] - self.PLOT_TIME_WINDOW_SECONDS, self.xdata[-1])

    def start(self):
        if self.started:
            return
        self.started = True
        self.timer.start()
        self.workout.start(qt_signal_emitter=self.workout_qt_emitter)

    def stop(self):
        if not self.started:
            return
        self.started = False
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
        self.distance_label.setText('%d revs' % distance)
        if len(self.workout.torque) > 0:
            self.ydata = self.ydata[1:] + [self.workout.torque.values[-1]]
            self.xdata = self.xdata[1:] + [self.workout.torque.timestamps[-1]]
            self.update_plot()

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

    def draw_and_cache_plot_background(self, force_draw):
        #self.canvas.axes.clear()
        self.canvas.axes.set_ylim(self.PLOT_MIN_Y, self.PLOT_MAX_Y)
        #self.canvas.axes.grid()
        self.canvas.axes.set_axis_off()
        #self.canvas.axes.get_xaxis().set_visible(False)
        #self.canvas.axes.get_yaxis().set_visible(False)

        if force_draw:
            self.canvas.draw()
        else:
            self.canvas.draw_idle()
        self.canvas.background = self.canvas.copy_from_bbox(self.canvas.axes.bbox)

    def init_plot(self):
        with self.redraw_lock:
            # Draw a blank plot and cache the background.
            self.draw_and_cache_plot_background(force_draw=True)
            # Return a reference to the plot and its current size. The size is used to force a full redraw if the window
            # in resized.
            plot_refs = self.canvas.axes.plot(self.xdata, self.ydata, linewidth=1.0, color='#4cadda') #color='#E9E9E9')
            plot_size = (self.canvas.axes.bbox.width, self.canvas.axes.bbox.height)
            return plot_refs[0], plot_size

    def update_plot(self):
        self.update_plot_2()
        # Update data and adjust visible window along the X axis.
        with self.redraw_lock:
            if not self.PLOT_FAST_DRAWING:
                self.torque_plot.set_ydata(self.ydata)
                self.torque_plot.set_xdata(self.xdata)
                self.canvas.axes.set_xlim(self.xdata[-1] - self.PLOT_TIME_WINDOW_SECONDS, self.xdata[-1])
                self.canvas.draw_idle()
            else:
                # Force a full redraw if the window has been resized.
                current_size = (self.canvas.axes.bbox.width, self.canvas.axes.bbox.height)
                if current_size != self.old_size:
                    self.torque_plot.set_xdata([None])
                    self.torque_plot.set_ydata([None])
                    self.draw_and_cache_plot_background(force_draw=True)
                    self.old_size = current_size

                self.torque_plot.set_ydata(self.ydata)
                self.torque_plot.set_xdata(self.xdata)
                self.canvas.axes.set_xlim(self.xdata[-1] - self.PLOT_TIME_WINDOW_SECONDS, self.xdata[-1])

                # Fast drawing. Restore the cached background, and draw the plot line.
                self.canvas.restore_region(self.canvas.background)
                self.canvas.axes.draw_artist(self.torque_plot)
                self.canvas.blit(self.canvas.axes.bbox)


data_source = ds.CsvFile(
    "C:\\Users\\checo\\Desktop\\rower\\2020-08-28 22h49m22s.csv",
    sample_delay=True,
    threaded=True
)

#data_source = ds.PiGpioClient(ip_address='192.168.1.130', pigpio_port=9876, gpio_pin_number=17)
#print('Connected!')
#sys.argv += ['--style', 'windowsvista']
app = QtWidgets.QApplication(sys.argv)
w = RowingMonitorMainWindow(data_source)
#w.resize(600, 800)
app.exec_()
