import base64

import cv2
import numpy as np


class Webcam:

    def __init__(
        self,
        camera_index=0,
    ):
        self.camera_index = (
            camera_index
        )

        self.camera = None

    def open(self):

        if self.camera:
            return

        self.camera = cv2.VideoCapture(
            self.camera_index,
            cv2.CAP_DSHOW,
        )

        if not self.camera.isOpened():

            self.camera.release()

            self.camera = None

            raise RuntimeError(
                "Não foi possível abrir a webcam."
            )

        self.camera.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            960,
        )

        self.camera.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            540,
        )

        for _ in range(5):
            self.camera.read()

    def capture(
        self,
        as_bytes=False,
    ):

        self.open()

        success, frame = (
            self.camera.read()
        )

        if not success:

            raise RuntimeError(
                "Falha ao capturar webcam."
            )

        success, encoded = (
            cv2.imencode(
                ".jpg",
                frame,
                [
                    cv2.IMWRITE_JPEG_QUALITY,
                    70,
                ],
            )
        )

        if not success:

            raise RuntimeError(
                "Falha ao codificar webcam."
            )

        data = encoded.tobytes()

        if as_bytes:
            return data

        return base64.b64encode(
            data
        ).decode("utf-8")

    def close(self):

        if self.camera:

            self.camera.release()
            self.camera = None
