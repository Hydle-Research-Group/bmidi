<img src="assets/bmidi.png">

bmidi is a node-based MIDI animation system for Blender, built in Python.

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

Create a new Blender project inside the root of this repository, and open the `main.py` file inside the "Script" tab. Run the file with `Alt-P` or use the run button located right next to the file name, launching bmidi's node editor.

## Using `bmidi`'s Node Editor

bmidi's node editor contains various node types to animate MIDI data.

- `MIDI Data`: the "root" node of the graph, containing the MIDI file and data.
- `MIDI Data Filter`: a node for filtering input MIDI data based on a specific note and channel.
- `Frame Collection`: a node for animating objects given the input MIDI data.

### MIDI Data Node

`MIDI Data` nodes contain a MIDI file and have an output for the parsed MIDI data. There are controls for generating object keyframes, including a "frame offset" input for offsetting the animation start.

**Clicking "Generate Keyframes" will set the timeline to `-1`, reset the animation data for all specified objects, then generate the frames.**

### MIDI Data Filter Node

`MIDI Data Filter` nodes filter input MIDI data based on a specified note and channel, outputting the filtered data.

### Frame Collection Node

`Frame Collection` nodes allow you to describe a set of frames that occur during certain triggers (e.g., when a note starts) 

These frames act either on a specific object, or a _target prefix_, where target prefixes are in the format `[prefix][note number]`. For example, an object might be named `Drum60`, so it's prefix would be `Drum` and bmidi would append `[note number]` to the end. 

## Free & Open-Source

bmidi is 100% free with no drawbacks or limitations. There is no "premium" version; you get the latest and greatest, all licensed under the GPL-3.0.

All source code is public, to anyone. There is no "hidden mechanism" included in this repository; every reference and used factor exists completely and fully.
