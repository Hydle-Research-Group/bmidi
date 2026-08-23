<img src="assets/bmidi.png">

bmidi is a Python-based automatic key-framing tool for MIDI data, allowing users to create MIDI-driven animations in Blender.

## Installing `bmidi`

bmidi is not available as a full Blender addon (for now), so creating a clone of this repository is necessary for usage.

### 1. Clone The Repo

Clone this repository into the desired folder with:

```sh
git clone https://github.com/Hydle-Research-Group/bmidi.git
```

### 2. Install The Python Requirements

Find the Blender Python executable by typing the following in the Blender console: 

```python
import sys
print(sys.executable)
```

Input the following into the terminal (ensure the current working directory is located in the repository root):

```sh
'<your blender python path>' -m pip install -r requirements.txt
```

You may have to ensure `pip` actually exists by first using:

```sh
'<your blender python path>' -m ensurepip
```

Then upgrade it with:

```sh
'<your blender python path>' -m pip install --upgrade pip
```

### 3. Run `main.py`

Create a new Blender project inside the root of this repository, and open the `main.py` file inside the "Script" tab. Run the file with `Alt-P` or use the run button located right next to the file name, launching bmidi's panel.

## Using `bmidi`

bmidi's user interface consists of panel with controls for frame generation.

- You can add or remove an item with the "+" or "-" buttons located in the top right of the panel.
- Items contain "events" or individual things that occur every time a MIDI note happens. 
- An item has a prefix for the name of the object; events target the object prefix + note (e.g. `Drum25`).

For all items, there is a `Channel` dropdown for selecting the specific channel that controls the objects. `Note Range Start` and `Note Range End` will allow notes between that range. 

Additionally, if `Use Block List` is selected, you can create a comma separated list of notes to block. The syntax supports notes (`X, Y, Z`), and ranges (`X-Y, Y-Z`).

**Clicking "Generate Keyframes" will set the timeline to `-1`, reset the animation data for all composition and controller objects, then generate the frames.**

## Capabilites

There are a collection of demo videos in [this YouTube playlist](https://www.youtube.com/playlist?list=PLRZuj2NaHK4KhIysZkML9mRQQlm8HeguG) showcasing what bmidi is capable of. Additionally, all music is original.

## Free & Open-Source

bmidi is 100% free with no drawbacks or limitations. There is no "premium" version; you get the latest and greatest, all licensed under the GPL-3.0.

All source code is public, to anyone. There is no "hidden mechanism" included in this repository; every reference and used factor exists completely and fully.
