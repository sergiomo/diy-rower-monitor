The DIY Smart Rower Monitor
===========================

Overview
--------
![screenshot](https://github.com/sergiomo/diy-rower-monitor/blob/master/screenshot.gif?raw=true)

This is the main monitor app for my DIY Smart Rower project. The gist of it is to turn a cheap magnetic rowing machine into a smart rower that provides detailed real-time rowing performance stats with only $25 worth of electronic components, and no soldering skills required [^1] .

For more details, see [the blog](https://diy-smart-rower.blogspot.com/2020/07/how-to-make-diy-smart-rower.html).

[^1]: Rowing machine not included :)
 
Installation
------------
1. Set up a Raspberry PI and sensors on your rower as described in [the blog](https://diy-smart-rower.blogspot.com/2020/07/how-to-make-diy-smart-rower.html).
2. Launch the pigpio daemon on the Pi with `sudo pigpiod -b 10000 -p 9876`
3. Log into to your router's management portal and identify the Pi's IP address.
4. Open `rower_monitor/my_config.yaml` in a text editor and update the IP address and pin number to match your setup.
5. In the config file, enter the location on your computer where you want your rowing data to be stored. For cloud saves, point to a directory managed by the Box, Dropbox, etc. desktop clients.
6. Install Python 3.8 or above on your computer.
7. Install the python dependencies with `pip install requirements.txt`.
8. Run the app with `python3 app.py`