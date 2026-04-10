import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from waveshare_epd import epd1in54
from PIL import Image


class EpaperDisplay:
    def __init__(self):
        self.epd = epd1in54.EPD()
        self.epd.init()
        self.epd.Clear(0xFF)  # clear to white

    def show(self, image: Image.Image) -> None:
        """Display a PIL Image. Image must be 200x200 mode '1'."""
        buf = self.epd.getbuffer(image)
        self.epd.display(buf)

    def sleep(self) -> None:
        """Put display into low-power sleep mode."""
        self.epd.sleep()

    def wake_and_show(self, image: Image.Image) -> None:
        """Re-initialize display (wake from sleep), show image, then sleep."""
        self.epd.init()
        self.show(image)
        self.sleep()
