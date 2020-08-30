from PyQt5 import QtCore, QtWidgets, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import sys
import random
import matplotlib
matplotlib.use('Qt5Agg')
matplotlib.pyplot.style.use('ggplot')

import data_sources as ds
import workout as wo

import time

class MplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


class RowingMonitorMainWindow(QtWidgets.QMainWindow):

    PLOT_VISIBLE_SAMPLES = 200
    PLOT_MIN_Y = -10
    PLOT_MAX_Y = 55

    GUI_FONT = QtGui.QFont('Inconsolata', 16)

    def __init__(self, data_source, *args, **kwargs):
        super(RowingMonitorMainWindow, self).__init__(*args, **kwargs)

        self.workout = wo.WorkoutMetricsTracker(data_source)

        # Connect workut emitter to UI update
        self.workout._qt_emitter.updated.connect(self.ui_callback)

        # Setup main window layout
        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        self.app_layout = QtWidgets.QVBoxLayout(self.main_widget)

        # Build button bar
        self.button_bar_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton('Start')
        self.stop_button = QtWidgets.QPushButton('Stop')
        # Appearance
        self.start_button.setFont(self.GUI_FONT)
        self.stop_button.setFont(self.GUI_FONT)
        # Add to main window
        self.button_bar_layout.addWidget(self.start_button)
        self.button_bar_layout.addWidget(self.stop_button)
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
        self.app_layout.addLayout(self.stats_bar_layout)

        # Add chart
        # fig = Figure(figsize=(10, 4), dpi=300, tight_layout=True)
        # fig.axes = fig.add_subplot(111)
        # super(MplCanvas, self).__init__(fig)

        self.canvas = MplCanvas(self, width=10, height=4, dpi=100)
        self.app_layout.addWidget(self.canvas)

        #########################################################################S
        self.xdata = [0 for i in range(self.PLOT_VISIBLE_SAMPLES)]
        self.ydata = [None for i in range(self.PLOT_VISIBLE_SAMPLES)]

        # We need to store a reference to the plotted line
        # somewhere, so we can apply the new data to it.
        self._plot_ref, self.old_size = self.init_plot()
        self.canvas.draw_idle()
        #########################################################################

        # Set interaction behavior
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)

        # Setup a timer to trigger the redraw by calling update_plot.
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.timer_tick)

        self.show()

    def start(self):
        self.start_timestamp = QtCore.QTime.currentTime()  # TODO: start timestamp is when the first encoder pulse occurs
        self.timer.start()
        self.workout.start(None)

    def stop(self):
        self.timer.stop()
        self.workout.stop()

    def ui_callback(self):
        # Update distance
        distance = self.workout.num_flywheel_revolutions
        self.distance_label.setText('%d revs' % distance)
        if len(self.workout.torque) > 0:
            self.ydata = self.ydata[1:] + [self.workout.torque.values[-1]]
            self.xdata = self.xdata[1:] + [self.workout.torque.timestamps[-1]]
            self.update_plot()

    def timer_tick(self):
        # Workout time
        time_since_start = self.start_timestamp.secsTo(QtCore.QTime.currentTime())
        minutes = time_since_start // 60
        seconds = time_since_start % 60
        time_string = '%d:%02d' % (minutes, seconds)
        self.time_label.setText(time_string)

    def _set_cache_plot_background(self):
        self.canvas.axes.clear()
        self.canvas.axes.set_ylim(self.PLOT_MIN_Y, self.PLOT_MAX_Y)
        self.canvas.axes.grid()
        self.canvas.axes.set_axis_off()
        self.canvas.draw()
        self.canvas.background = self.canvas.copy_from_bbox(self.canvas.axes.bbox)

    def init_plot(self):
        self._set_cache_plot_background()
        # First time we have no plot reference, so do a normal plot.
        # .plot returns a list of line <reference>s, as we're
        # only getting one we can take the first element.
        plot_refs = self.canvas.axes.plot(self.xdata, self.ydata, 'r')
        plot_size = (self.canvas.axes.bbox.width, self.canvas.axes.bbox.height)
        return plot_refs[0], plot_size

    def update_plot(self):
        # We have a reference, we can use it to update the data for that line.
        self._plot_ref.set_ydata(self.ydata)
        self._plot_ref.set_xdata(self.xdata)
        self.canvas.axes.set_xlim(self.xdata[-1]-8, self.xdata[-1])

        #self.canvas.draw_idle()
        #return

        current_size = (self.canvas.axes.bbox.width, self.canvas.axes.bbox.height)
        if current_size != self.old_size:
            self._set_cache_plot_background()
            self.old_size = current_size

        # Trigger the canvas to update and redraw.
        self.canvas.restore_region(self.canvas.background)
        self.canvas.axes.draw_artist(self._plot_ref)
        self.canvas.blit(self.canvas.axes.bbox)

csv_source = ds.CsvFile(None, "C:\\Users\\checo\\Desktop\\rower\\2020-08-28 22h49m22s.csv",  sample_delay=True)


app = QtWidgets.QApplication(sys.argv)
w = RowingMonitorMainWindow(csv_source)
app.exec_()
