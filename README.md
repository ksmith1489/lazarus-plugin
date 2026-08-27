# 3DPrintSaver.com

3DPrintSaver.com helps recover failed 3D prints whether the partial print is still attached or must be carefully re-seated on the bed.

It generates resume G-code locally inside OctoPrint from the original G-code file, the measured print height, and the detected layer structure of that file. The plugin then guides the user through safe alignment before resuming.

## Install From URL

In OctoPrint:

1. Open `Settings`
2. Open `Plugin Manager`
3. Choose `Get More...`
4. Select `...from URL`
5. Paste this URL:

```text
https://github.com/ksmith1489/lazarus-plugin/archive/refs/tags/v2.0.1.zip
```

6. Install and restart OctoPrint when prompted

The internal OctoPrint plugin id remains `lazarus` so existing installs keep their settings and install ID.

## What It Does

The plugin:

- reads the original G-code file locally inside OctoPrint;
- uses the measured height of the incomplete print to identify the likely resume layer;
- accounts for differing initial layer heights and spiral vase mode;
- generates a resume G-code file for inspection and execution;
- optionally prints an experimental landing pad and insertion-safe tagged supports for a loose failed print;
- calculates a real-world alignment target;
- guides the user through safe coordinate recovery and final nozzle alignment.

The original G-code file is not uploaded to the license service for resume generation.

## Recovery Workflow

Typical use looks like this:

1. Select the original G-code file from OctoPrint storage or a local device.
2. Measure the incomplete print and enter the lower left/right height.
3. Generate the resume file and inspect the preview.
4. Establish a safe coordinate state.
5. Move to the calculated alignment target.
6. Align the nozzle to the incomplete print.
7. Download or execute the generated resume sequence.

## Firmware Support

3DPrintSaver.com supports:

- standard OctoPrint printer communication;
- Marlin-based printers;
- Klipper-based printers;
- optional Moonraker / Klipper workflows through a user-provided local Moonraker address.

## Licensing And Activation

Installation is free, but resume generation, download, upload, and execution require an active subscription.

One subscription activates the web app, Android app, and OctoPrint plugin on up to 3 devices.

License v2 activation uses checkout email + license key + install ID. Existing install-ID-only validation remains supported for older installs.

Activation, pricing, and legal information:

- Activation: https://3dprintsaver.com/activate
- License: https://3dprintsaver.com/license
- Terms: https://3dprintsaver.com/terms
- Privacy: https://3dprintsaver.com/privacy

## Source And Support

- Source: https://github.com/ksmith1489/lazarus-plugin
- Product site: https://3dprintsaver.com
- Support: Ken@3dprintsaver.com

## Development Notes

Regression test:

```bash
python -m unittest tests.test_resume_engine
```

Syntax / import sanity check:

```bash
python -m compileall octoprint_lazarus
```
