import os
import json
import requests
import pytest

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration test skipped: RUN_INTEGRATION_TESTS not set"
)
def test_prediction_service():
    """
    Integration test for the model serving API.
    Ensures that the MLflow model server is running and responding correctly.
    """

    url = "http://localhost:5001/invocations"
    headers = {"Content-Type": "application/json"}

    input_path = os.path.join("data", "sample_input.json")
    assert os.path.exists(input_path), f"Missing test input file: {input_path}"

    with open(input_path) as f:
        data = json.load(f)

    response = requests.post(url, headers=headers, json=data)
    assert response.status_code == 200, f"Prediction service failed: {response.text}"
