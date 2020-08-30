from PyQt5 import QtCore, QtWidgets, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import sys
import random
import matplotlib
matplotlib.use('Qt5Agg')
matplotlib.pyplot.style.use('ggplot')


class MplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

    # def my_update(self):
    #     """
    #     Efficiently update the figure, without needing to redraw the
    #     "background" artists.
    #     """
    #     self.fig.canvas.restore_region(self.background)
    #     self.ax.draw_artist(self.points)
    #     self.fig.canvas.blit(self.fig.bbox)


class RowingMonitorMainWindow(QtWidgets.QMainWindow):

    PLOT_VISIBLE_SAMPLES = 40
    PLOT_MIN_Y = -10
    PLOT_MAX_Y = 55

    GUI_FONT = QtGui.QFont('Inconsolata', 16)

    def __init__(self, *args, **kwargs):
        super(RowingMonitorMainWindow, self).__init__(*args, **kwargs)

        # Setup main window layout
        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        self.app_layout = QtWidgets.QVBoxLayout(self.main_widget)

        # Build button bar, and add it to the top of the main window
        self.button_bar_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton('Start')
        self.stop_button = QtWidgets.QPushButton('Stop')
        self.start_button.setFont(self.GUI_FONT)
        self.stop_button.setFont(self.GUI_FONT)
        self.button_bar_layout.addWidget(self.start_button)
        self.button_bar_layout.addWidget(self.stop_button)
        self.app_layout.addLayout(self.button_bar_layout)

        # Build workout stats bar
        self.stats_bar_layout = QtWidgets.QHBoxLayout()
        self.workout_label = QtWidgets.QLabel('Workout')
        self.time_label = QtWidgets.QLabel('0:00')
        self.distance_label = QtWidgets.QLabel('0 revs')

        self.workout_label.setFont(self.GUI_FONT)
        self.time_label.setFont(self.GUI_FONT)
        self.distance_label.setFont(self.GUI_FONT)
        self.workout_label.setAlignment(QtCore.Qt.AlignCenter)
        self.time_label.setAlignment(QtCore.Qt.AlignCenter)
        self.distance_label.setAlignment(QtCore.Qt.AlignCenter)

        self.stats_bar_layout.addWidget(self.workout_label)
        self.stats_bar_layout.addWidget(self.time_label)
        self.stats_bar_layout.addWidget(self.distance_label)
        self.app_layout.addLayout(self.stats_bar_layout)

        # Add chart
        self.canvas = MplCanvas(self, width=16, height=4, dpi=100)
        self.app_layout.addWidget(self.canvas)

        #########################################################################S
        self.xdata = list(range(self.PLOT_VISIBLE_SAMPLES))
        self.ydata = [None for i in range(self.PLOT_VISIBLE_SAMPLES)]

        # We need to store a reference to the plotted line
        # somewhere, so we can apply the new data to it.
        self._plot_ref = None
        self.update_plot()
        #########################################################################

        # Set interaction behavior
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)

        # Setup a timer to trigger the redraw by calling update_plot.
        self.timer = QtCore.QTimer()
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.timer_tick)

        self.show()

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def timer_tick(self):
        self.update_data()
        self.update_plot()

    def update_data(self):
        # Drop off the first y element, append a new one.
        self.ydata = self.ydata[1:] + [random.randint(0, 10)]

    def _set_cache_plot_background(self):
        self.canvas.axes.clear()
        self.canvas.axes.set_ylim(self.PLOT_MIN_Y, self.PLOT_MAX_Y)
        self.canvas.axes.set_xlim(0, self.PLOT_VISIBLE_SAMPLES)
        self.canvas.axes.grid()
        self.canvas.axes.set_axis_off()
        self.canvas.draw()
        self.canvas.background = self.canvas.copy_from_bbox(self.canvas.axes.bbox)

    def update_plot(self):
        # Note: we no longer need to clear the axis.
        if self._plot_ref is None:
            self._set_cache_plot_background()
            # First time we have no plot reference, so do a normal plot.
            # .plot returns a list of line <reference>s, as we're
            # only getting one we can take the first element.
            plot_refs = self.canvas.axes.plot(self.xdata, self.ydata, 'r')
            self._plot_ref = plot_refs[0]
            self.old_size = (self.canvas.axes.bbox.width, self.canvas.axes.bbox.height)
        else:
            # We have a reference, we can use it to update the data for that line.
            self._plot_ref.set_ydata(self.ydata)

        current_size = (self.canvas.axes.bbox.width, self.canvas.axes.bbox.height)
        if current_size != self.old_size:
            self._set_cache_plot_background()
            self.old_size = current_size

        # Trigger the canvas to update and redraw.
        self.canvas.restore_region(self.canvas.background)
        self.canvas.axes.draw_artist(self._plot_ref)
        self.canvas.blit(self.canvas.axes.bbox)


app = QtWidgets.QApplication(sys.argv)
w = RowingMonitorMainWindow()
app.exec_()
