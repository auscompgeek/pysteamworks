from ctre import CANTalon
from wpilib import DoubleSolenoid, Compressor

from collections import deque
import numpy as np

class Winch:

    winch_motor = CANTalon
    rope_lock_solenoid = DoubleSolenoid
    compressor = Compressor

    def __init__(self):
        super().__init__()

        # self.last_currents = deque(maxlen=5)

    def on_rope_engaged(self):
        """Return wether the current is over 5 as a boolean"""
        # self.last_currents.append(self.winch_motor.getOutputCurrent())
        # return np.mean(list(self.last_currents)) >= 2
        return self.winch_motor.getOutputCurrent() > 10

    def on_touchpad_engaged(self):
        """Return wether the current is over 2 as a boolean"""
        return self.winch_motor.getOutputCurrent() > 35

    def rotate_winch(self, value):
        """Rotate winch motor with half speed"""
        self.winch_motor.set(value)

    def piston_open(self):
        """Open piston"""
        self.rope_lock_solenoid.set(DoubleSolenoid.Value.kReverse)

    def piston_close(self):
        """Close piston"""
        self.rope_lock_solenoid.set(DoubleSolenoid.Value.kForward)

    def disable_compressor(self):
        self.compressor.setClosedLoopControl(False)

    def enable_compressor(self):
        self.compressor.setClosedLoopControl(True)

    def setup(self):
        """Run just after createObjects.
        Useful if you want to run something after just once after the
        robot code is started, that depends on injected variables"""

    def on_enable(self):
        """Run every time the robot transitions to being enabled"""
        self.enable_compressor()

    def on_disable(self):
        """Run every time the robot transitions to being disabled"""
        pass

    def execute(self):
        """Run at the end of every control loop iteration"""
        pass
