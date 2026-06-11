import json

from planetar_eo.bus.zmesg import Envelope, parse


def test_envelope_roundtrip_minimal():
    e = Envelope(topic="eo.detection", payload=b'{"hi":1}')
    buf = e.serialize()
    back = parse(buf)
    assert back.topic == "eo.detection"
    assert back.payload == b'{"hi":1}'
    assert back.source == "planetar-eo"
    assert back.id == e.id
    assert back.created_at_ns == e.created_at_ns


def test_envelope_with_metadata():
    payload = json.dumps({"source_id": "chek.shipspoint", "conf": 0.81}).encode()
    e = Envelope(
        topic="eo.detection",
        payload=payload,
        schema_name="planetar.eo.detection.v1",
        schema_version=1,
        correlation_id="abc-123",
    )
    back = parse(e.serialize())
    assert back.schema_name == "planetar.eo.detection.v1"
    assert back.schema_version == 1
    assert back.correlation_id == "abc-123"
    assert json.loads(back.payload)["source_id"] == "chek.shipspoint"
