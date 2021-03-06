from components.vision import Vision
from components.bno055 import BNO055
from utilities.kalman import Kalman

from collections import deque

import numpy as np
import time

class VisionFilter:

    vision = Vision
    bno055 = BNO055

    state_vector_size = 2

    # the initial uncertainty in the vision rate
    init_dx_variance = 0.01

    # the vision sensor noise
    vision_x_variance = 0.0005

    # the variance in the unknown acceleration impulse
    acceleration_variance = 0.25

    loop_dt = 1/50

    reset_thresh = 0.2

    def __init__(self):
        pass

    def setup(self):
        self.reset()

    def reset(self):

        # starting state
        x_hat = np.array([self.vision.x, 0]).reshape(-1, 1)

        P = np.zeros(shape=(self.state_vector_size, self.state_vector_size))
        P[0][0] = VisionFilter.vision_x_variance
        P[1][1] = VisionFilter.init_dx_variance
        Q = (np.array(
                [[self.loop_dt**4/4, self.loop_dt**3/3],[self.loop_dt**3/2, self.loop_dt**2]]).
                reshape(self.state_vector_size, self.state_vector_size)*self.acceleration_variance)
        self.last_vision = self.vision.x
        self.last_vision_time = self.vision.time

        # error vision and error rate of change of vision are correlated
        R = np.array([[VisionFilter.vision_x_variance, VisionFilter.vision_x_variance],
            [VisionFilter.vision_x_variance, VisionFilter.vision_x_variance*6]]).reshape(self.state_vector_size, self.state_vector_size)

        self.filter = Kalman(x_hat, P, Q, R)

        self.imu_deque = deque(maxlen=50, iterable=[self.get_heading_state()])

    def get_heading_state(self):
        return np.array([self.bno055.getHeading(), self.bno055.getHeadingRate()]).reshape(-1, 1)

    def on_enable(self):
        self.reset()

    def predict(self, timestep=1):
        """Predict what the measurement should be in the next timestep.
        :param timestep: the number of timesteps in the past that we are predicting forward *from*"""

        F = np.identity(self.state_vector_size)
        F[0][1] = self.loop_dt
        B = np.identity(self.state_vector_size)

        self.imu_deque.append(self.get_heading_state())

        u = Vision.rad_to_vision_units(self.imu_deque[-timestep] - self.imu_deque[-timestep-1])

        self.filter.predict(F, u, B)

    def update(self):

        x = self.vision.x
        dx = (self.vision.x-self.last_vision)/(self.vision.time-self.last_vision_time)

        H = np.identity(self.state_vector_size)
        z = np.array([x, dx]).reshape(-1, 1)

        self.filter.update(z, H)

        self.last_vision = self.vision.x
        self.last_vision_time = self.vision.time

    def execute(self):
        if self.vision.time == 0:
            return
        timesteps_since_vision = int((time.time() - self.vision.time)/50)
        if timesteps_since_vision > 10:
            return
        elif abs(self.vision.x - self.filter.x_hat[0][0]) > self.reset_thresh:
            self.reset()
        self.predict()
        if self.vision.time != self.last_vision_time:
            self.filter.roll_back(timesteps_since_vision)
            self.update()
            for i in range(timesteps_since_vision):
                self.predict(timestep=timesteps_since_vision-i)

    @property
    def x(self):
        return self.filter.x_hat[0][0]

    @property
    def dx(self):
        return self.filter.x_hat[1][0]

    @property
    def angle(self):
        return -(self.x*self.horizontal_fov/2)
