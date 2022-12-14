#!/usr/bin/env python

import sys

from drone_status import DroneStatus

# Import the messages we're interested in sending and receiving
from geometry_msgs.msg import Twist  	 # for sending commands to the drone
from std_msgs.msg import Empty       	 # for land/takeoff/emergency
from ardrone_autonomy.msg import Navdata # for receiving navdata feedback
# Import the ROS libraries, and load the manifest file which through <depend package=... /> will give us access to the project dependencies
import roslib; roslib.load_manifest('ardrone_tutorials')
import rospy

# Load the DroneController class, which handles interactions with the drone
from drone_controllers import BasicDroneController, PIDController


# TF Libraries
import tf2_ros
from geometry_msgs.msg import Twist

import time

import signal

import sys

COMMAND_PERIOD = 100 #ms

def exit_handler(signum, frame):
 	print("Emergency")
	drone.SendEmergency()
	time.sleep(2)
	exit(1)
	
# Setup the application
if __name__=='__main__':
	topic_name = "ardrone"
	if len(sys.argv) > 1:
		topic_name = sys.argv[1]

	signal.signal(signal.SIGINT, exit_handler)

	if topic_name == "ardrone":
		payload_frame = "ar_marker_1"
		dropoff_frame = "dropoff frame"
		drone_frame = "ar_marker_2"
		landing_zone = "landing frame"
	else:
		payload_frame = "payload1"
		dropoff_frame = "dropoff1"
		drone_frame = "sjtu_drone"
		landing_zone = "nist_elevated_floor_120"
	
	# Firstly we setup a ros node, so that we can communicate with the other packages
	rospy.init_node('ardrone_shipping_system')

	# Create controller to communicate with the drone
	drone = BasicDroneController(topic_name)
	# Create PDI controller to navigate drone
	navigator = PIDController()

	time.sleep(10)

	# Take off
	print("Taking off")
	drone.SendTakeoff()
	time.sleep(8)
	drone.status = DroneStatus.Flying
	drone.SetCommand(0, 0, 0, 0)
	
	print("Hovering")
	time.sleep(2)

	# Navigate to first payload
	print("Navigating to first payload")
	drone.navigate(navigator, drone_frame, payload_frame)
#	time.sleep(0.5)	
	drone.SetCommand(0, 0, 0, 0)
	
	print("Hovering")
	time.sleep(3)

	# # Descend down
	print("Descend")
	drone.Descend()

	print("Hovering")
        time.sleep(3)

	# Enable gripper
	# Ascend
	print("Ascend")	
	drone.Ascend()
	
	# # Navigate to drop-off
	print("Navigating to Dropoff")
	navigator = PIDController()
	drone.navigate(navigator, drone_frame, dropoff_frame)
	drone.SetCommand(0, 0, 0, 0)
	time.sleep(5)
	# # Disable gripper

	# # Navigate to landing spot
	print("Navigating to Landing")
	navigator = PIDController()
	drone.navigate(navigator, drone_frame, landing_zone)
	drone.SetCommand(0, 0, 0, 0)
	time.sleep(3)
	
	# Land
	print("Landing Drone")
	drone.SendLand()
	time.sleep(5)

	rospy.signal_shutdown('All Done!')
