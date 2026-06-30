import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "octoprint_lazarus" / "resume_engine.py"
SPEC = importlib.util.spec_from_file_location("lazarus_resume_engine_test", MODULE_PATH)
resume_engine = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = resume_engine
SPEC.loader.exec_module(resume_engine)


SAMPLE_GCODE = """G1 E3 F1800
G1 X193.08 E13.6 F3000
G1 Y110.08 E0.32 F3000
G1 X108.08 E13.6 F3000
G1 Y193.08 E13.28 F3000
G1 X110.08 E0.32 F3000
G1 Y111.08 E13.12 F3000
G1 X111.08 Z0
G1 X114.08
G1 X20 Y5 Z0.4 F30000
G1 X220 Y5 E8 F1800
G1 Z1 F600
SET_PRINT_STATS_INFO CURRENT_LAYER=1
; MACHINE_START_GCODE_END
M106 S0
M106 P2 S0
SET_PRESSURE_ADVANCE ADVANCE=0.01; Override pressure advance value
; Filament start gcode
;VT0
M106 P3 S0
G90
G21
M83 ; use relative distances for extrusion
; CHANGE_LAYER
; Z_HEIGHT: 0.4
; LAYER_HEIGHT: 0.4
G1 E-3 F1800
TIMELAPSE_TAKE_FRAME
G92 E0
SET_PRINT_STATS_INFO CURRENT_LAYER=1
M106 S0
M106 P2 S0
M204 S6000
G1 Z.4 F30000
G1 X128.951 Y183.656
G1 E3 F1800
G1 F2100
M204 S500
G1 X128.513 Y183.32 E.06474
G1 X125.086 Y180.316 E.53417
G1 X124.695 Y179.925 E.06479
G1 X174.936 Y149.45 E.33878
; CHANGE_LAYER
; Z_HEIGHT: 0.72
; LAYER_HEIGHT: 0.32
G1 F3300
G1 X174.544 Y147.489 E-2.85
G1 E-.15 F1800
TIMELAPSE_TAKE_FRAME
G92 E0
SET_PRINT_STATS_INFO CURRENT_LAYER=2
M204 S10000
G17
G3 Z.8 I1.217 J0 P1 F30000
G1 X169.821 Y139.148
G1 Z.72
G1 E3 F1800
G1 F4242.491
M204 S5000
G1 X169.853 Y139.185 E.0047
G1 X175.832 Y129.093 E.40981
; CHANGE_LAYER
; Z_HEIGHT: 26.32
; LAYER_HEIGHT: 0.32
G1 F4242.491
G1 X177.737 Y130.998 E-2.85
G1 E-.15 F1800
TIMELAPSE_TAKE_FRAME
G92 E0
SET_PRINT_STATS_INFO CURRENT_LAYER=82
G17
G3 Z26.4 I1.217 J0 P1 F30000
G1 X169.821 Y139.148
G1 Z26.32
G1 E3 F1800
G1 F4242.491
M204 S5000
G1 X169.853 Y139.185 E.00468
G1 X157.948 Y132.166 E.26423
G1 X160.556 Y133.051 E.26427
G1 X163.026 Y134.269 E.2642
G1 X165.315 Y135.799 E.26423
G1 X167.386 Y137.614 E.26425
G1 X169.122 Y139.595 E.25272
; WIPE_START
M204 S10000
G1 X170.242 Y141.252 E-2.85001
; WIPE_END
G1 E-.14999 F1800
G1 X177.235 Y144.31 Z26.72 F30000
G1 X185.904 Y148.102 Z26.72
G1 Z26.32
G1 E3 F1800
; FEATURE: Inner wall
G1 F4242.491
M204 S5000
G1 X186.192 Y152.5 E.42295
"""

TAGGED_SUPPORT_GCODE = """; layer_height = 0.2
; first_layer_height = 0.2
G90
M83
;LAYER:0
G0 X0 Y0 Z0.2
;TYPE:WALL-OUTER
G1 X30 Y0 E1.0 F1200
G1 X30 Y30 E1.0
G1 X0 Y30 E1.0
G1 X0 Y0 E1.0
;TYPE:SUPPORT
G0 X40 Y0
G1 X42 Y0 E0.2
G0 X10 Y10
G1 X12 Y10 E0.2
;LAYER:1
G0 Z0.4
;TYPE:WALL-OUTER
G0 X8 Y8
G1 X22 Y8 E0.5
G1 X22 Y22 E0.5
;TYPE:SUPPORT
G0 X40 Y0
G1 X42 Y0 E0.2
G0 X25 Y10
G1 X27 Y10 E0.2
;TYPE:SUPPORT-INTERFACE
G0 X55 Y0
G1 X57 Y0 E0.2
;LAYER:2
G0 Z0.6
;TYPE:WALL-OUTER
G0 X10 Y10
G1 X20 Y10 E0.4
;TYPE:SUPPORT
G0 X40 Y0
G1 X42 Y0 E0.2
"""


class ResumeEngineRegressionTests(unittest.TestCase):
    def test_infer_layer_height_prefers_repeated_nominal_value(self) -> None:
        self.assertAlmostEqual(resume_engine.infer_layer_height(SAMPLE_GCODE), 0.32, places=5)

    def test_collect_layer_z_values_ignores_arc_hop_heights(self) -> None:
        printing_z_values = resume_engine._collect_layer_z_values(SAMPLE_GCODE, printing_only=True)
        motion_z_values = resume_engine._collect_layer_z_values(SAMPLE_GCODE, printing_only=False)

        self.assertEqual(printing_z_values, [0.4, 0.72, 26.32])
        self.assertNotIn(0.8, motion_z_values)
        self.assertNotIn(26.4, motion_z_values)

    def test_build_resumed_gcode_anchors_on_true_print_plane(self) -> None:
        result = resume_engine.build_resumed_gcode(
            SAMPLE_GCODE,
            firmware="klipper",
            print_height_mm=26.4,
            alignment_side="left",
        )

        self.assertAlmostEqual(result["layer_height"], 0.32, places=5)
        self.assertAlmostEqual(result["initial_layer_height"], 0.4, places=5)
        self.assertAlmostEqual(result["resume_z"], 26.32, places=3)
        self.assertAlmostEqual(result["datum"]["x"], 157.948, places=3)
        self.assertAlmostEqual(result["datum"]["y"], 132.166, places=3)
        self.assertAlmostEqual(result["datum"]["z"], 26.32, places=3)
        self.assertIn("; Computed resume height (RH): 26.320 mm", result["resumed_text"])
        self.assertIn("; Datum: X157.948 Y132.166 Z26.320", result["resumed_text"])
        self.assertNotIn("; Datum: X169.821 Y139.148 Z26.400", result["resumed_text"])
        self.assertIn("G1 X169.853 Y139.185 E.00468", result["resumed_text"])

    def test_build_landing_pad_copies_first_printable_layer(self) -> None:
        result = resume_engine.build_landing_pad_gcode(
            SAMPLE_GCODE,
            park_position=dict(x=90, y=290, z=250),
        )

        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["first_layer_z"], 0.4, places=3)
        self.assertAlmostEqual(result["landing_pad_height"], 0.4, places=3)
        self.assertGreater(result["move_count"], 0)
        self.assertIn("; MACHINE_START_GCODE_END", result["landing_pad_text"])
        self.assertIn("; --- BEGIN COPIED SLICER START + FIRST LAYER ---", result["landing_pad_text"])
        self.assertIn("G1 X128.951 Y183.656", result["landing_pad_text"])
        self.assertIn("G1 E3 F1800", result["landing_pad_text"])
        self.assertIn("G1 X128.513 Y183.32 E.06474", result["landing_pad_text"])
        self.assertIn("G1 X220 Y5 E8", result["landing_pad_text"])
        self.assertNotIn("; Z_HEIGHT: 0.72", result["landing_pad_text"])
        self.assertNotIn("G1 X174.544 Y147.489 E-2.85", result["landing_pad_text"])
        self.assertNotIn("G1 X169.853 Y139.185 E0.00470", result["landing_pad_text"])
        self.assertNotIn("SET_PRINT_STATS_INFO CURRENT_LAYER=2", result["landing_pad_text"])
        self.assertIn("G0 X90 Y290 F6000", result["landing_pad_text"])

    def test_build_resumed_gcode_uses_landing_pad_height_offset(self) -> None:
        result = resume_engine.build_resumed_gcode(
            SAMPLE_GCODE,
            firmware="klipper",
            print_height_mm=26.8,
            height_offset_mm=0.4,
            alignment_side="left",
        )

        self.assertAlmostEqual(result["measured_print_height"], 26.8, places=3)
        self.assertAlmostEqual(result["height_offset"], 0.4, places=3)
        self.assertAlmostEqual(result["resume_z"], 26.32, places=3)
        self.assertIn("; Landing pad height offset: 0.400 mm", result["resumed_text"])
        self.assertIn("; Computed resume height (RH): 26.320 mm", result["resumed_text"])

    def test_tagged_support_rebuild_outputs_compact_support_paths_only(self) -> None:
        result = resume_engine.build_landing_pad_gcode(
            TAGGED_SUPPORT_GCODE,
            include_supports=True,
            include_support_interface=True,
            support_build_height=0.6,
            support_clearance_mm=0.8,
        )

        self.assertEqual(result["support_move_count"], 2)
        self.assertEqual(result["rejected_insertion_support_moves"], 2)
        self.assertEqual(result["rejected_disconnected_support_moves"], 1)
        self.assertIn("; --- BEGIN COMPACT TAGGED SUPPORT REBUILD ---", result["landing_pad_text"])
        self.assertIn("G1 X42 Y0 E0.2", result["landing_pad_text"])
        self.assertNotIn("G1 X22 Y8 E0.5", result["landing_pad_text"])
        self.assertNotIn("G1 X57 Y0 E0.2", result["landing_pad_text"])

    def test_tagged_support_rebuild_fails_clearly_without_support_labels(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "does not contain recognizable support feature labels",
        ):
            resume_engine.build_landing_pad_gcode(
                SAMPLE_GCODE,
                include_supports=True,
                support_build_height=26.72,
            )

    def test_support_toggle_off_preserves_existing_landing_pad_output(self) -> None:
        default_result = resume_engine.build_landing_pad_gcode(TAGGED_SUPPORT_GCODE)
        disabled_result = resume_engine.build_landing_pad_gcode(
            TAGGED_SUPPORT_GCODE,
            include_supports=False,
        )

        self.assertEqual(
            default_result["landing_pad_text"],
            disabled_result["landing_pad_text"],
        )
        self.assertEqual(disabled_result["support_move_count"], 0)

    def test_cumulative_wide_base_rejects_support_inside_lower_footprint(self) -> None:
        result = resume_engine.build_landing_pad_gcode(
            TAGGED_SUPPORT_GCODE,
            include_supports=True,
            support_build_height=0.6,
            support_clearance_mm=0.8,
        )

        self.assertGreaterEqual(result["rejected_insertion_support_moves"], 2)
        self.assertNotIn("G1 X27 Y10 E0.2", result["landing_pad_text"])

    def test_support_interface_without_bed_root_is_rejected(self) -> None:
        interface_only = """\
;LAYER:0
G90
M82
G1 Z0.2 F1200
;TYPE:WALL-OUTER
G1 X0 Y0 F3000
G1 X10 Y0 E1 F1200
G1 X10 Y10 E2
G1 X0 Y10 E3
G1 X0 Y0 E4
;LAYER:1
G1 Z0.4 F1200
;TYPE:SUPPORT-INTERFACE
G1 X40 Y40 F3000
G1 X45 Y40 E5 F1200
"""
        result = resume_engine.build_landing_pad_gcode(
            interface_only,
            include_supports=True,
            support_build_height=0.4,
            support_clearance_mm=0.8,
            require_bed_connected_supports=True,
        )

        self.assertEqual(result["support_move_count"], 0)
        self.assertEqual(result["rejected_disconnected_support_moves"], 1)
        self.assertNotIn("G1 X45 Y40 E", result["landing_pad_text"])


if __name__ == "__main__":
    unittest.main()
