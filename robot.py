#!/usr/bin/env python3

import magicbot
import wpilib
from wpilib import XboxController

from ctre import CANTalon

from components.range_finder import RangeFinder
from components.chassis import Chassis
from components.bno055 import BNO055
from components.gearalignmentdevice import GearAlignmentDevice
from components.geardepositiondevice import GearDepositionDevice
from components.vision import Vision
from components.winch import Winch
from automations.manipulategear import ManipulateGear
from automations.profilefollower import ProfileFollower
from automations.winchautomation import WinchAutomation
from automations.vision_filter import VisionFilter
from automations.range_filter import RangeFilter

from utilities.profilegenerator import generate_trapezoidal_trajectory

from networktables import NetworkTable

import logging

import math
import time


class Robot(magicbot.MagicRobot):

    chassis = Chassis
    gearalignmentdevice = GearAlignmentDevice
    geardepositiondevice = GearDepositionDevice
    winch_automation = WinchAutomation
    manipulategear = ManipulateGear
    vision = Vision
    winch = Winch
    profilefollower = ProfileFollower
    range_finder = RangeFinder
    vision_filter = VisionFilter
    range_filter = RangeFilter

    def createObjects(self):
        '''Create motors and stuff here'''

        # Objects that are created here are shared with all classes
        # that declare them. For example, if I had:
        # self.elevator_motor = wpilib.TalonSRX(2)
        # here, then I could have
        # class Elevator:
        #     elevator_motor = wpilib.TalonSRX
        # and that variable would be available to both the MyRobot
        # class and the Elevator class. This "variable injection"
        # is especially useful if you want to certain objects with
        # multiple different classes.

        # create the imu object
        self.bno055 = BNO055()

        # the "logger" - allows you to print to the logging screen
        # of the control computer
        self.logger = logging.getLogger("robot")
        # the SmartDashboard network table allows you to send
        # information to a html dashboard. useful for data display
        # for drivers, and also for plotting variables over time
        # while debugging
        self.sd = NetworkTable.getTable('SmartDashboard')

        # boilerplate setup for the joystick
        self.joystick = wpilib.Joystick(0)
        self.gamepad = XboxController(1)
        self.pressed_buttons_js = set()
        self.pressed_buttons_gp = set()
        self.drive_motor_a = CANTalon(2)
        self.drive_motor_b = CANTalon(5)
        self.drive_motor_c = CANTalon(4)
        self.drive_motor_d = CANTalon(3)
        self.gear_alignment_motor = CANTalon(14)
        self.winch_motor = CANTalon(11)
        self.winch_motor.setInverted(True)
        self.rope_lock_solenoid = wpilib.DoubleSolenoid(forwardChannel=0,
                reverseChannel=1)
        # self.rope_lock_solenoid = wpilib.DoubleSolenoid(forwardChannel=3,
        #         reverseChannel=4)
        self.gear_push_solenoid = wpilib.Solenoid(2)
        self.gear_drop_solenoid = wpilib.Solenoid(3)
        # self.gear_push_solenoid = wpilib.DoubleSolenoid(forwardChannel=1, reverseChannel=2)
        # self.gear_drop_solenoid = wpilib.Solenoid(0)

        self.test_trajectory = generate_trapezoidal_trajectory(
                0, 0, 3, 0, Chassis.max_vel, 1, -1, Chassis.motion_profile_freq)

        self.throttle = 1.0
        self.direction = 1.0

        self.led_dio = wpilib.DigitalOutput(1)

        self.compressor = wpilib.Compressor()

    def putData(self):
        # update the data on the smart dashboard
        # put the inputs to the dashboard
        self.sd.putNumber("gyro", self.bno055.getHeading())
        self.sd.putNumber("vision_x", self.vision.x)
        # if self.manipulategear.current_state == "align_peg":
        self.sd.putNumber("range", self.range_finder.getDistance())
        self.sd.putNumber("climbCurrent", self.winch_motor.getOutputCurrent())
        self.sd.putNumber("rail_pos", self.gearalignmentdevice.get_rail_pos())
        self.sd.putNumber("error_differential",
                self.drive_motor_a.getClosedLoopError()-
                self.drive_motor_c.getClosedLoopError())
        self.sd.putNumber("velocity", self.chassis.get_velocity())
        self.sd.putNumber("left_speed_error", self.drive_motor_a.getClosedLoopError())
        self.sd.putNumber("right_speed_error", self.drive_motor_c.getClosedLoopError())
        self.sd.putNumber("x_throttle", self.chassis.inputs[0])
        self.sd.putNumber("z_throttle", self.chassis.inputs[2])
        self.sd.putNumber("filtered_x", self.vision_filter.x)
        self.sd.putNumber("filtered_dx", self.vision_filter.dx)
        self.sd.putNumber("vision_filter_x_variance", self.vision_filter.filter.P[0][0])
        self.sd.putNumber("vision_filter_dx_variance", self.vision_filter.filter.P[1][1])
        self.sd.putNumber("vision_filter_covariance", self.vision_filter.filter.P[0][1])
        self.sd.putNumber("filtered_range", self.range_filter.filter.x_hat[0][0])
        self.sd.putNumber("range_filter_variance", self.range_filter.filter.P[0][0])
        self.sd.putNumber("time", time.time())

    def teleopInit(self):
        '''Called when teleop starts; optional'''
        self.sd.putString("state", "stationary")
        self.gearalignmentdevice.reset_position()
        self.geardepositiondevice.retract_gear()
        self.geardepositiondevice.lock_gear()
        self.profilefollower.stop()
        self.winch.enable_compressor()
        self.vision.enabled = False
        print("TELEOP INIT RANGE: %s" % (self.range_finder.getDistance()))
        print("TELEOP INIT FILTER RANGE: %s" % (self.range_filter.range))

    def autonomousPeriodic(self):
        self.putData()

    def disabledInit(self):
        self.sd.putBoolean("log", False)

    def disabledPeriodic(self):
        self.putData()
        self.sd.putString("state", "stationary")
        self.vision_filter.execute()
        self.range_filter.execute()

    def teleopPeriodic(self):
        '''Called on each iteration of the control loop'''
        self.putData()

        try:
            if self.debounce(8, gamepad=True) or self.debounce(1):
                self.manipulategear.engage(force=True)

        except:
            self.onException()

        try:
            if self.debounce(7, gamepad=True) or self.debounce(3):
                self.winch_automation.engage(force=True)
        except:
            self.onException()

        try:
            if self.debounce(7):
                self.sd.putBoolean("log", True)
        except:
            self.onException()

        # try:
        #     if self.debounce(10):
        #         # stop the winch
        #         if self.winch_automation.is_executing:
        #             self.winch_automation.done()
        #         self.winch.piston_open()
        #         self.winch.rotate_winch(0)

        #         if self.manipulategear.is_executing:
        #             self.manipulategear.done()
        #         self.gearalignmentdevice.reset_position()
        #         self.sd.putString("state", "stationary")
        # except:
        #     self.onException()

        try:
            if self.debounce(2):
                if self.manipulategear.is_executing:
                    self.manipulategear.done()
                self.gearalignmentdevice.reset_position()
                self.geardepositiondevice.retract_gear()
                self.geardepositiondevice.lock_gear()
        except:
            self.onException()

        try:
            if self.debounce(4):
                if self.winch_automation.is_executing:
                    self.winch_automation.done()
                self.winch.rotate_winch(0)
        except:
            self.onException()

        try:
            if self.debounce(5):
                if self.winch_automation.is_executing:
                    self.winch_automation.done()
                self.winch.rotate_winch(1.0)
                self.winch.piston_close()
        except:
            self.onException()

        try:
            if self.debounce(6):
                self.winch.locked = not self.winch.locked
        except:
            self.onException()

        try:
            if self.debounce(12):
                self.geardepositiondevice.retract_gear()
                self.geardepositiondevice.lock_gear()
        except:
            self.onException()

        try:
            if self.debounce(10):
                # self.geardepositiondevice.push_gear()
                # self.geardepositiondevice.drop_gear()
                self.manipulategear.engage(initial_state="forward_closed", force=True)
        except:
            self.onException()

        try:
            if self.debounce(12):
                self.geardepositiondevice.retract_gear()
                self.geardepositiondevice.lock_gear()
        except:
            self.onException()


        if (not self.gamepad.getRawButton(5) and
                not self.gamepad.getRawButton(6) and
                not self.gamepad.getRawAxis(3) > 0.9):
            self.throttle = 1
            self.direction = 1
            self.sd.putString("camera", "front")
        elif self.gamepad.getRawButton(5):
            # reverse
            self.throttle = 1
            self.direction = -1
            self.sd.putString("camera", "back")
        elif self.gamepad.getRawButton(6):
            # slow down
            self.throttle = 0.3
            self.direction = 1
            self.sd.putString("camera", "front")
        elif self.gamepad.getRawAxis(3) > 0.9:
            self.throttle = 0.3
            self.direction = -1
            self.sd.putString("camera", "back")

        if self.joystick.getPOV() == 90:
            if not self.manipulategear.is_executing:
                self.gearalignmentdevice.move_right()
        elif self.joystick.getPOV() == 270:
            if not self.manipulategear.is_executing:
                self.gearalignmentdevice.move_left()
        # elif self.joystick.getPOV() == 0 or self.joystick.getPOV() == 180:
        #     if not self.manipulategear.is_executing:
        #         self.gearalignmentdevice.set_position(0)

        if 1.5/self.chassis.velocity_to_native_units < abs(self.chassis.get_velocity()) and not self.manipulategear.is_executing:
            self.gearalignmentdevice.set_position(0)

        self.chassis.inputs = [(
            self.direction
            * -rescale_js(self.gamepad.getRawAxis(1), deadzone=0.05, exponential=30)),
                    - rescale_js(self.joystick.getX(), deadzone=0.05, exponential=1.2),
                    -rescale_js(self.gamepad.getRawAxis(4), deadzone=0.05, exponential=30, rate=0.6 if self.throttle == 1 else 1),
                    self.throttle
                    ]
        # self.chassis.inputs = [(
        #     self.direction
        #     * -rescale_js(self.gamepad.getRawAxis(1), rate=0.3, deadzone=0.05, exponential=15)),
        #             - rescale_js(self.joystick.getX(), deadzone=0.05, exponential=1.2),
        #             -rescale_js(self.gamepad.getRawAxis(4), deadzone=0.05, exponential=15.0, rate=0.2),
        #             self.throttle
        #             ]
        self.vision.led_on = self.joystick.getRawButton(11)

    # the 'debounce' function keeps tracks of which buttons have been pressed
    def debounce(self, button, gamepad=False):
        device = None
        if gamepad:
            pressed_buttons = self.pressed_buttons_gp
            device = self.gamepad
        else:
            pressed_buttons = self.pressed_buttons_js
            device = self.joystick
        if device.getRawButton(button):
            if button in pressed_buttons:
                return False
            else:
                pressed_buttons.add(button)
                return True
        else:
            pressed_buttons.discard(button)
            return False

# see comment in teleopPeriodic for information
def rescale_js(value, deadzone=0.0, exponential=0.0, rate=1.0):
    value_negative = 1.0
    if value < 0:
        value_negative = -1.0
        value = -value
    # Cap to be +/-1
    if abs(value) > 1.0:
        value /= abs(value)
    # Apply deadzone
    if abs(value) < deadzone:
        return 0.0
    elif exponential == 0.0:
        value = (value - deadzone) / (1 - deadzone)
    else:
        a = math.log(exponential + 1) / (1 - deadzone)
        value = (math.exp(a * (value - deadzone)) - 1) / exponential
    return value * value_negative * rate

if __name__ == '__main__':
    wpilib.run(Robot)
