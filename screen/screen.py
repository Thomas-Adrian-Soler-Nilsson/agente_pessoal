import base64
import io

import numpy as np
import pyautogui
from PIL import Image


class Screen:

    def __init__(
        self,
        max_width=1280,
        quality=60,
    ):
        self.max_width = max_width
        self.quality = quality

    def capture(
        self,
        as_bytes=False,
    ):

        screenshot = (
            pyautogui.screenshot()
        )

        image = screenshot.convert(
            "RGB"
        )

        width, height = image.size

        if width > self.max_width:

            new_height = int(
                height
                * self.max_width
                / width
            )

            image = image.resize(
                (
                    self.max_width,
                    new_height,
                ),
                Image.Resampling.LANCZOS,
            )

        buffer = io.BytesIO()

        image.save(
            buffer,
            format="JPEG",
            quality=self.quality,
            optimize=True,
        )

        data = buffer.getvalue()

        if as_bytes:
            return data

        return base64.b64encode(
            data
        ).decode("utf-8")

    def capture_array(self):

        screenshot = (
            pyautogui.screenshot()
        )

        image = np.array(
            screenshot.convert(
                "L"
            )
        )

        return image