#!/usr/bin/env python

# A basic drone controller class for the tutorial "Up and flying with the AR.Drone and ROS | Getting Started"
# https://github.com/mikehamer/ardrone_tutorials_getting_started

# This class implements basic control functionality which we will be using in future tutorials.
# It can command takeoff/landing/emergency as well as drone movement
# It also tracks the drone state based on navdata feedback

# Import the ROS libraries, and load the manifest file which through <depend package=... /> will give us access to the project dependencies
import roslib; roslib.load_manifest('ardrone_tutorials')
import rospy

from gazebo_msgs.srv import GetModelState

# Import the messages we're interested in sending and receiving
from geometry_msgs.msg import Twist  	 # for sending commands to the drone
from std_msgs.msg import Empty       	 # for land/takeoff/emergency
from ardrone_autonomy.msg import Navdata # for receiving navdata feedback

# An enumeration of Drone Statuses
from drone_status import DroneStatus

# TF Libraries
import tf2_ros
from geometry_msgs.msg import Twist

# Some Constants
COMMAND_PERIOD = 100 #ms
import time

class BasicDroneController(object):
	def __init__(self, topic_name):
		# Holds the current drone status
		self.status = DroneStatus.Landed
		
		self.topic_name = topic_name

		# Subscribe to the /ardrone/navdata topic, of message type navdata, and call self.ReceiveNavdata when a message is received
		self.subNavdata = rospy.Subscriber('/' + topic_name + '/navdata',Navdata,self.ReceiveNavdata) 
		self.altitude = -1
		
		# Allow the controller to publish to the /ardrone/takeoff, land and reset topics
		self.pubLand    = rospy.Publisher('/' + topic_name + '/land', Empty, queue_size=10)
		self.pubTakeoff = rospy.Publisher('/' + topic_name + '/takeoff', Empty, queue_size=10)
		self.pubReset   = rospy.Publisher('/' + topic_name + '/reset', Empty, queue_size=10)
		
		# Allow the controller to publish to the /cmd_vel topic and thus control the drone
		self.pubCommand = rospy.Publisher('/cmd_vel', Twist, queue_size=10)

		# Setup regular publishing of control packets
		self.command = Twist()
		self.commandTimer = rospy.Timer(rospy.Duration(COMMAND_PERIOD/1000.0),self.SendCommand)

		# Land the drone if we are shutting down
#		rospy.on_shutdown(self.SendLand)

	def ReceiveNavdata(self,navdata):
		# Although there is a lot of data in this packet, we're only interested in the state at the moment	
		self.status = navdata.state
		self.altitude = navdata.altd

	def SendTakeoff(self):
		# Send a takeoff message to the ardrone driver
		# Note we only send a takeoff message if the drone is landed - an unexpected takeoff is not good!
		self.pubTakeoff.publish(Empty())


	def SendLand(self):
		# Send a landing message to the ardrone driver
		# Note we send this in all states, landing can do no harm
		self.pubLand.publish(Empty())

	def GetAltitude(self):
		if self.topic_name == "ardrone":
			return self.altitude
		else:
			return self.getGazeboState("sjtu_drone").pose.position.z

	def Descend(self):
		while self.GetAltitude() > 1:
			self.SetCommand(roll=0, pitch=0, yaw_velocity=0, z_velocity=-1)
		self.SetCommand(0, 0, 0, 0)

	def Ascend(self):
		while self.GetAltitude() < 2:
			self.SetCommand(roll=0, pitch=0, yaw_velocity=0, z_velocity=1)
		self.SetCommand(0, 0, 0, 0)

	def SendEmergency(self):
		# Send an emergency (or reset) message to the ardrone driver
		self.pubReset.publish(Empty())

	def SetCommand(self,roll=0,pitch=0,yaw_velocity=0,z_velocity=0):
		# Called by the main program to set the current command
		self.command.linear.x  = pitch
		self.command.linear.y  = roll
		self.command.linear.z  = z_velocity
		self.command.angular.z = yaw_velocity

	def SendCommand(self,event):
		# The previously set command is then sent out periodically if the drone is flying
		if self.status == DroneStatus.Flying or self.status == DroneStatus.GotoHover or self.status == DroneStatus.Hovering:
			self.pubCommand.publish(self.command)

	# Basic Up and Down Flight
	def run(self):
		rate = rospy.Rate(1.0)
		while not rospy.is_shutdown():
			self.SendTakeoff()
			rospy.sleep(1)
			self.SendLand()
			rate.sleep()
	
	def navigate(self, PID, source_frame, target_frame):
		PID.setInitialTime(time.time())

		tfBuffer = tf2_ros.Buffer()
		tfListener = tf2_ros.TransformListener(tfBuffer)
		
		rate = rospy.Rate(1.0)
		
		while not rospy.is_shutdown():
			try:
				e_x, e_y = self.get_error(source_frame, target_frame)
				x, y, z, Reached = PID.step(e_x, e_y, 0)
				if Reached:
					break
			# pitch = 1 -> forward
			# roll = 1 -> left
				self.SetCommand(y, x, 0)
			# this is automatically called self.SendCommand()
			except Exception as e:
				print(e)
				print("Skipped a frame", source_frame, target_frame)	
			rate.sleep()
	
	def getGazeboState(self, model_name):
		model_coordinates = rospy.ServiceProxy('/gazebo/get_model_state', GetModelState)
		quad_coordinates = model_coordinates(model_name,'')
		z = quad_coordinates.pose.position.z
		y = quad_coordinates.pose.position.y
		x = quad_coordinates.pose.position.x
		return quad_coordinates

	def get_error(self, source_frame, target_frame):
		if self.topic_name == "ardrone": # real drone
			tfBuffer = tf2_ros.Buffer()
	                tfListener = tf2_ros.TransformListener(tfBuffer)

			
			transform = tfBuffer.lookup_transform(source_frame, target_frame, rospy.Time())
			e_t_x = transform.transform.translation.x # x_f - x_c
			e_t_y = transform.transform.translation.y # y_f - y_c
			# e_t_z = transform.transform.translation.z # z_f - z_c
			return e_t_x, e_t_y
		else: # in simulator
			source_coordinates = self.getGazeboState(source_frame)
			target_coordinates = self.getGazeboState(target_frame)

			e_t_x = target_coordinates.pose.position.x - source_coordinates.pose.position.x
			e_t_y = target_coordinates.pose.position.y - source_coordinates.pose.position.y

			return e_t_x, e_t_y

			

class PIDController(object):
	def __init__(self):
		# self.iniState = iniState
		self.K_I = 0.01
		self.K_D = 0.5
		self.K_P = 0.3
		self.error_history = 0

		self.errorThreshold = 0.15
		self.last_error_x =0 
		self.last_error_y =0 
		self.last_error_z =0 

		self.integral_x = 0
		self.integral_y = 0
		self.integral_z = 0

		self.vel_max = 0.7
		self.vel_scale = 1

	def setInitialTime(self,t=0):
		self.last_time = t
	
	def step(self, e_t_x, e_t_y, e_t_z):
		shouldStop = False	
		# z_c = currentState.pose.position.z
		# y_c = currentState.pose.position.y
		# x_c = currentState.pose.position.x

		# z_f = finalState[2]
		# y_f = finalState[1]
		# x_f = finalState[0]


		P_x = self.K_P * e_t_x 
		P_y = self.K_P * e_t_y 
		P_z = self.K_P * e_t_z 

		self.current_time = time.time()

		delta_time = self.current_time - self.last_time

		
		self.integral_x = 0.8*self.integral_x + e_t_x * delta_time
		self.integral_y = 0.8*self.integral_y + e_t_y * delta_time	
		self.integral_z = 0.8*self.integral_z + e_t_z * delta_time

		

		I_x = self.K_I * self.integral_x
		I_y = self.K_I * self.integral_y
		I_z = self.K_I * self.integral_z

		der_x = (e_t_x - self.last_error_x) /delta_time
		der_y = (e_t_y - self.last_error_y) /delta_time
		der_z = (e_t_z - self.last_error_z) /delta_time

		D_x = self.K_D * der_x
		D_y = self.K_D * der_y
		D_z = self.K_D * der_z
		
		self.last_time = self.current_time
		self.last_error_x = e_t_x
		self.last_error_y = e_t_y
		self.last_error_z = e_t_z

		O_x = P_x + I_x + D_x
		O_y = P_y + I_y + D_y
		O_z = P_z + I_z + D_z
		
		O_x = max(-self.vel_max, min(self.vel_max, O_x * self.vel_scale))
		O_y = max(-self.vel_max, min(self.vel_max, O_y * self.vel_scale))
		O_z = max(-self.vel_max, min(self.vel_max, O_z * self.vel_scale))
		print("Error: x:{} y:{} z:{}".format(e_t_x,e_t_y,e_t_z))
		#print("Current: {} Dest: {}".format([x_c,y_c,z_c],[x_f,y_f,z_f]))

		if((abs(e_t_x) < self.errorThreshold) and (abs(e_t_y) < self.errorThreshold)):
			print("Stopping")			
			shouldStop = True 
		print("Output velocity: O_x:{} O_y:{} O_z:{}".format(O_x,O_y,O_z))
		return O_x,O_y,O_z,shouldStop
		
