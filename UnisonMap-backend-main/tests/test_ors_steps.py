import pytest

from app.services.ors_routing import ORSService


def _service_without_init() -> ORSService:
    return ORSService.__new__(ORSService)


def test_steps_parsing_returns_expected_schema():
    service = _service_without_init()
    response = {
        "routes": [
            {
                "geometry": {
                    "coordinates": [
                        [-110.0, 29.0],
                        [-110.0005, 29.0005],
                        [-110.001, 29.001],
                    ]
                },
                "summary": {"distance": 150.6, "duration": 75.4},
                "segments": [
                    {
                        "steps": [
                            {
                                "instruction": "Gira a la izquierda",
                                "name": "Pasillo A",
                                "distance": 50.4,
                                "duration": 20.2,
                                "way_points": [0, 1],
                            },
                            {
                                "instruction": "Continúa recto",
                                "name": "",
                                "distance": 100.2,
                                "duration": 55.2,
                                "way_points": [1, 2],
                            },
                        ]
                    }
                ],
            }
        ]
    }

    result = service._procesar_respuesta_ors(response)

    assert result["steps_count"] == 2
    assert len(result["instrucciones"]) == 2
    first_step = result["instrucciones"][0]
    assert first_step["orden"] == 0
    assert "Pasillo A" in first_step["texto"]
    assert first_step["distance_m"] == 50
    assert first_step["duration_s"] == 20
    assert first_step["location"] == {"lat": 29.0, "lng": -110.0}
    assert result["current_step_index"] == 0


def test_missing_steps_returns_empty_list_but_still_route():
    service = _service_without_init()
    response = {
        "routes": [
            {
                "geometry": {
                    "coordinates": [
                        [-110.0, 29.0],
                        [-110.0005, 29.0005],
                    ]
                },
                "summary": {"distance": 80, "duration": 40},
                "segments": [{}],
            }
        ]
    }

    result = service._procesar_respuesta_ors(response)

    assert result["instrucciones"] == []
    assert result["steps_count"] == 0
    assert result["distancia_m"] == 80
    assert result["duracion_s"] == 40


def test_steps_with_waypoints_map_to_location_field():
    service = _service_without_init()
    response = {
        "routes": [
            {
                "geometry": {
                    "coordinates": [
                        [-110.0, 29.0],
                        [-110.0005, 29.0005],
                        [-110.001, 29.001],
                        [-110.0015, 29.0015],
                    ]
                },
                "summary": {"distance": 200, "duration": 100},
                "segments": [
                    {
                        "steps": [
                            {
                                "instruction": "Gira a la derecha",
                                "name": "Pasillo B",
                                "distance": 70,
                                "duration": 30,
                                "way_points": [2, 3],
                            }
                        ]
                    }
                ],
            }
        ]
    }

    result = service._procesar_respuesta_ors(response)

    assert result["steps_count"] == 1
    step = result["instrucciones"][0]
    assert step["location"] == {"lat": 29.001, "lng": -110.001}
    assert step["texto"].startswith("Gira a la derecha")
    assert step["distance_m"] == 70
    assert step["duration_s"] == 30
