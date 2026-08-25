from __future__ import annotations

"""V4L2 / CSI SC3336 на Luckfox. На ПК это тот же OpenCV, но с явным CAP_V4L2."""

from terminal.camera.opencv_camera import OpenCVCamera


class V4L2Camera(OpenCVCamera):
    name = "v4l2"
