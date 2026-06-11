import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.make_teleport_world import _load_pose, build_teleport_world


def test_load_pose_picks_nearest_time_and_team(tmp_path):
    telemetry = tmp_path / "telemetry.jsonl"
    telemetry.write_text(
        "\n".join(
            [
                json.dumps({"t": 1.0, "cars": [{"team_id": "a", "x": 1, "y": 2, "heading": 0.1}]}),
                json.dumps({"t": 2.0, "cars": [{"team_id": "a", "x": 3, "y": 4, "heading": 0.2}]}),
                json.dumps({"t": 2.1, "cars": [{"team_id": "b", "x": 9, "y": 9, "heading": 0.9}]}),
            ]
        ),
        encoding="utf-8",
    )

    pose = _load_pose(telemetry, 1.8, team_id="a")

    assert pose["t"] == 2.0
    assert pose["x"] == 3.0
    assert pose["heading"] == 0.2


def test_build_teleport_world_rewrites_only_target_car(tmp_path):
    source = tmp_path / "track.wbt"
    source.write_text(
        """#VRML_SIM R2025a utf8
DEF car_1 CarPhoenix {
  name "car_1"
  translation 26.5 -26 0.4
}
DEF car_2 CarThunder {
  name "car_2"
  translation 26.5 -31.7 0.4
}
""",
        encoding="utf-8",
    )
    output = tmp_path / "jump.wbt"

    build_teleport_world(
        source,
        output,
        "car_1",
        {"x": 169.1234567, "y": 111.7654321, "heading": 1.5708},
        0.4,
    )

    text = output.read_text(encoding="utf-8")
    assert "translation 169.123457 111.765432 0.400000" in text
    assert "rotation 0 0 1 -1.570800000" in text
    assert "DEF car_2 CarThunder" in text
    assert "translation 26.5 -31.7 0.4" in text
