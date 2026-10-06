# LakeAgent build helper
# Makes a 256px .ico from a png/jpg you drop in this folder, then runs
# PyInstaller. Same pattern as the other tools in this workspace.
import os
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = ("icon.png", "icon.jpg", "icon.jpeg")
ICON = os.path.join(HERE, "icon.ico")


def make_icon():
    for name in SOURCES:
        source = os.path.join(HERE, name)
        if not os.path.exists(source):
            continue
        image = Image.open(source).convert("RGBA")
        image = image.resize((256, 256), Image.Resampling.LANCZOS)
        image.save(ICON, format="ICO", sizes=[(256, 256), (64, 64),
                                              (32, 32), (16, 16)])
        print("icon:", name, "->", ICON)
        return True
    if os.path.exists(ICON):
        print("using existing icon.ico")
        return True
    print("no icon.png / icon.jpg found, building without an icon")
    return False


def build():
    command = [sys.executable, "-m", "PyInstaller", "--onefile", "--windowed",
               "--name", "LakeAgent", "--clean", "main.py"]
    if os.path.exists(ICON):
        command += ["--icon", "icon.ico"]
    subprocess.run(command, cwd=HERE, check=True)

    print("\nBuild complete! Check the 'dist' folder.")
    print("The exe creates its 'lakeagent_data' folder next to itself the")
    print("first time it runs. Delete that folder to start fresh.")


if __name__ == "__main__":
    make_icon()
    build()