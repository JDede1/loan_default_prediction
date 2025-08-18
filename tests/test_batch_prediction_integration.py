import os
import subprocess
import pytest

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration test skipped: RUN_INTEGRATION_TESTS not set"
)
def test_batch_prediction_runs(tmp_path):
    output_path = tmp_path / "predictions.csv"

    result = subprocess.run(
        [
            "python", "src/batch_predict.py",
            "--model_name", "loan_default_model",
            "--alias", "staging",
            "--input_path", "data/batch_input.csv",
            "--output_path", str(output_path)
        ],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Batch prediction failed: {result.stderr}"
    assert output_path.exists()
