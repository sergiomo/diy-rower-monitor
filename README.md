# Rower Monitor Setup
1. Set up a Raspberry PI and sensors on your rower as described in [the blog](https://diy-smart-rower.blogspot.com/2020/07/how-to-make-diy-smart-rower.html).
2. Launch the pigpio daemon on the Pi with `sudo pigpiod -b 10000 -p 9876`
3. Log into to your router's management portal and identify the Pi's IP address.
4. Open `rower_monitor/my_config.yaml` in a text editor and update the IP address and pin number to match your setup.
5. In the config file, enter the location on your computer where you want your rowing data to be stored. For cloud saves, point to a directory managed by the Box, Dropbox, etc. desktop clients.
6. Install Python 3.8 or above on your computer.
7. Install the python dependencies with `pip install requirements.txt`.
8. Run the app with `python3 app.py`