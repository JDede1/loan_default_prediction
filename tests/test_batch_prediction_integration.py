import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration test skipped: RUN_INTEGRATION_TESTS not set",
)
def test_batch_prediction_runs(tmp_path):
    """
    Run batch prediction and verify that a predictions file
    (with timestamped name) is created successfully.
    Works in both MLflow registry (models:/...) and local mlruns fallback.
    """
    base_output = tmp_path / "predictions.csv"

    # Run batch prediction script
    result = subprocess.run(
        [
            "python",
            "src/batch_predict.py",
            "--model_name",
            "loan_default_model",
            "--alias",
            "staging",
            "--input_path",
            "data/batch_input.csv",
            "--output_path",
            str(base_output),
        ],
        capture_output=True,
        text=True,
    )

    # Ensure the process completed successfully
    assert (
        result.returncode == 0
    ), f"Batch prediction failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    # Accept both naming patterns: predictions_*.csv or preds_*.csv
    preds_files = list(Path(tmp_path).glob("predictions_*.csv")) + list(
        Path(tmp_path).glob("preds_*.csv")
    )

    # If no predictions file found, raise with debug context
    assert preds_files, (
        f"No predictions file found in {tmp_path}. "
        f"Stdout:\n{result.stdout}\nStderr:\n{result.stderr}\n"
        f"Current working dir: {os.getcwd()}\n"
        f"Contents of tmp_path: {[p.name for p in tmp_path.iterdir()]}"
    )
