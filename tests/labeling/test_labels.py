import pytest

from labeling.labels import to_silver_label


@pytest.mark.parametrize(
    ("csv_label", "expected"),
    [("phishing", "phishing"), ("clean", "benign"), ("suspicious", None), ("skip", None)],
)
def test_mapping_to_silver_labels(csv_label, expected):
    assert to_silver_label(csv_label) == expected


def test_normalises_case_and_space():
    assert to_silver_label(" Clean ") == "benign"


def test_unknown_label_rejected():
    with pytest.raises(ValueError):
        to_silver_label("benign")
