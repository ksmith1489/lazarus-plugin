---
layout: plugin

id: lazarus
title: Failed Print Resume Wizard
description: Resume failed 3D prints when the partial print is still attached to the bed.
authors:
- Kenneth B Smith
license: Proprietary - See LICENSE.txt

date: 2026-05-09

homepage: https://wizard.lazarus3dprint.com
source: https://github.com/ksmith1489/lazarus-plugin
archive: https://github.com/ksmith1489/lazarus-plugin/archive/refs/tags/v1.0.0.zip

privacypolicy: https://wizard.lazarus3dprint.com/privacy

tags:
- printing
- recovery
- gcode
- klipper
- moonraker
- marlin

compatibility:
  python: ">=3.7,<4"

attributes:
- cloud
- commercial
---

Failed Print Resume Wizard helps recover failed 3D prints when the partial print is still attached to the bed.

The plugin generates the resume G-code locally inside OctoPrint from the original G-code file, the measured print height, and the detected layer structure of that file. The original G-code is not uploaded to the Failed Print Resume Wizard service for processing.

Failed Print Resume Wizard includes a guided recovery workflow:

- select the original G-code from OctoPrint storage or your local device;
- enter the measured height of the saved print;
- generate a new resume file and a calculated alignment point;
- establish a safe starting coordinate state;
- align the nozzle to the saved print using OctoPrint motion controls;
- download or execute the generated resume sequence.

Printer movement remains user-controlled. Failed Print Resume Wizard does not automatically home Z into an existing print.

Optional Moonraker/Klipper support is included through a user-provided local Moonraker address.

Failed Print Resume Wizard uses `https://wizard.lazarus3dprint.com` for activation and subscription validation. If that service is unavailable, Failed Print Resume Wizard fails closed for resume generation and execution without causing OctoPrint itself to malfunction.

Failed Print Resume Wizard is commercial software and requires an active subscription for resume generation and execution. Pricing, activation, terms, license information, and privacy information are available here:

- https://wizard.lazarus3dprint.com/activate
- https://wizard.lazarus3dprint.com/license
- https://wizard.lazarus3dprint.com/terms
- https://wizard.lazarus3dprint.com/privacy
