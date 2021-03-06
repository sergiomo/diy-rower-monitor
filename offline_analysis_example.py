from rower_monitor import data_sources as ds
from rower_monitor import workout as wo
from rower_monitor import config_loader as cf
import time

import matplotlib.pyplot as plt

csv_source = ds.CsvFile(
    "C:\\Users\\checo\\Desktop\\rower\\2020-08-24 22h18m35s.csv",
    threaded=False,
    sample_delay=False,
)

config_data = cf.load_config()
workout = wo.WorkoutMetricsTracker(config=config_data, data_source=csv_source)
workout.start()
workout.stop()


print(workout.boat.position.values[-1])

work = [x.work_done_by_person / 5.0 for x in workout.person.strokes.values]
plt.plot(workout.person.torque.timestamps, workout.person.torque.values)
plt.scatter(workout.person.strokes.timestamps, work, s=1, c='red')
plt.show()


print('done')
exit()


plt.plot(workout.machine.flywheel_acceleration.timestamps, workout.machine.flywheel_acceleration.values)
plt.show()


plt.scatter(workout.machine.flywheel_speed.values[1:], workout.machine.flywheel_acceleration.values, s=1)
plt.show()

intercepts = [x.intercept for x in workout.machine.damping_models]
slopes = [x.slope for x in workout.machine.damping_models]
#plt.plot(intercepts)
plt.plot(slopes)
plt.show()

