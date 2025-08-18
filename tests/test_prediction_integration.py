import os
import json
import time
import pytest
import requests

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration test skipped: RUN_INTEGRATION_TESTS not set"
)
def test_prediction_service():
    """
    Integration test for the model serving API.
    Ensures that the MLflow model server is running and responding correctly.
    Includes retry logic since the container may take time to become ready.
    """

    # ✅ Use service name instead of localhost (matches docker-compose service: serve)
    url = "http://serve:5001/invocations"
    headers = {"Content-Type": "application/json"}

    input_path = os.path.join("data", "sample_input.json")
    assert os.path.exists(input_path), f"Missing test input file: {input_path}"

    with open(input_path) as f:
        data = json.load(f)

    # Retry up to 5 times with backoff to handle startup delay
    max_retries, last_err = 5, None
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            assert response.status_code == 200, f"Non-200 response: {response.text}"
            result = response.json()
            assert "predictions" in result, f"Missing 'predictions' in response: {result}"
            return  # ✅ success, exit test
        except Exception as e:
            last_err = e
            time.sleep(5)  # wait before retry

    pytest.fail(f"Prediction service test failed after {max_retries} retries. Last error: {last_err}")
