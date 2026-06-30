# The Helm v2.0.1

The Helm V2 now supports recovery when a failed print has come loose from the bed.

## Highlights

- Adds the experimental Loose From Bed workflow.
- Prints a first-layer landing pad with alignment guides before the part is re-seated.
- Optionally extracts compact slicer-tagged support paths up to the recovery height.
- Filters supports against the cumulative model insertion envelope.
- Removes support islands that are not connected back to the bed.
- Preserves the existing stuck-print workflow when the experimental option is disabled.

## Install

Install directly from OctoPrint's Plugin Manager using:

```text
https://github.com/ksmith1489/lazarus-plugin/archive/refs/tags/v2.0.1.zip
```

In OctoPrint:

1. Open `Settings`.
2. Open `Plugin Manager`.
3. Choose `Get More...`.
4. Select `...from URL`.
5. Paste the URL above.
6. Install and restart OctoPrint.

## Notes

- Support rebuilding requires recognizable slicer support labels.
- The loose-bed landing-pad and support workflow is marked experimental.
- The Helm remains proprietary commercial software.
