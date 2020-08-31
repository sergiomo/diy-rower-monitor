import data_sources as ds
import workout as wo
import time

import matplotlib.pyplot as plt


#csv_source = ds.CsvFile(None, "C:\\Users\\checo\\Desktop\\rower\\2020-06-10 09h54m05s.csv")
#csv_source = ds.CsvFile(None, "C:\\Users\\checo\\Desktop\\rower\\2020-06-22 21h39m58s.csv")
#csv_source = ds.CsvFile(None, "C:\\Users\\checo\\Desktop\\rower\\2020-06-20 17h25m29s.csv")
csv_source = ds.CsvFile(
    "C:\\Users\\checo\\Desktop\\rower\\2020-06-30 09h20m55s.csv",
    threaded=False,
    sample_delay=False,
)

workout = wo.WorkoutMetricsTracker(csv_source)
workout.start()
workout.stop()

workout.save('')
print(workout.num_flywheel_revolutions)

print('done')
exit()


plt.plot(workout.acceleration.timestamps, workout.acceleration.values)
plt.show()


plt.scatter(workout.speed.values[1:], workout.acceleration.values, s=1)
plt.show()

intercepts = [x.fitted_damping_model.intercept for x in workout.strokes.values]
slopes = [x.fitted_damping_model.slope for x in workout.strokes.values]
plt.plot(intercepts)
#plt.plot(slopes)
plt.show()

plt.plot(workout.torque.timestamps, workout.torque.values)
plt.show()
