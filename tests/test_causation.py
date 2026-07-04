"""Distributed-tracing wiring: eo.detection must point at its eo.frame.

The run loop publishes one eo.frame envelope per grabbed frame, then one
eo.detection envelope per detection derived from that frame. The detection's
`causation_id` must equal the frame envelope's id (dashed-UUID string form),
and both share `correlation_id` = the camera/source id.
"""
import json
import re

from planetar_eo.bus.zmesg import parse, uuid_str
from planetar_eo.cli import _detection_envelope, _frame_envelope

DASHED_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class _FakeShape:
    shape = (480, 640, 3)


class _FakeFrame:
    ts_ns = 1_700_000_000_000_000_000
    seq = 7
    image = _FakeShape()


class _FakeDetection:
    @staticmethod
    def as_dict():
        return {"source_id": "chek.shipspoint", "cls_name": "boat", "conf": 0.81}


def test_detection_causation_is_frame_envelope_id():
    frame_env = _frame_envelope("chek.shipspoint", _FakeFrame(), n_detections=1)
    det_env = _detection_envelope("chek.shipspoint", _FakeDetection(), uuid_str(frame_env.id))

    assert det_env.causation_id == uuid_str(frame_env.id)
    assert DASHED_UUID.match(det_env.causation_id)
    # correlation groups frame + detections under the camera id
    assert frame_env.correlation_id == "chek.shipspoint"
    assert det_env.correlation_id == "chek.shipspoint"
    # frames are roots — no causation
    assert frame_env.causation_id == ""


def test_causation_survives_the_wire():
    frame_env = _frame_envelope("chek.shipspoint", _FakeFrame(), n_detections=1)
    det_env = _detection_envelope("chek.shipspoint", _FakeDetection(), uuid_str(frame_env.id))
    back = parse(det_env.serialize())
    assert back.causation_id == uuid_str(frame_env.id)
    assert json.loads(back.payload)["cls_name"] == "boat"


def test_uuid_str_is_canonical_dashed_hex():
    frame_env = _frame_envelope("chek.shipspoint", _FakeFrame(), n_detections=0)
    s = uuid_str(frame_env.id)
    assert DASHED_UUID.match(s)
    assert bytes.fromhex(s.replace("-", "")) == frame_env.id
