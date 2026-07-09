"""Tests unitaires de ml/evaluate.py (Livrable 5/8)."""

import numpy as np

from ml.evaluate import best_threshold_by_f1, compute_metrics


def test_compute_metrics_perfect_separation():
    y_true = np.array([0, 0, 0, 1, 1])
    y_proba = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
    metrics = compute_metrics(y_true, y_proba, threshold=0.5)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["pr_auc"] == 1.0
    assert metrics["true_positives"] == 2
    assert metrics["false_positives"] == 0


def test_compute_metrics_confusion_counts():
    y_true = np.array([0, 1, 1, 0])
    y_proba = np.array([0.9, 0.1, 0.6, 0.4])  # 1 FP (idx0), 1 FN (idx1)
    metrics = compute_metrics(y_true, y_proba, threshold=0.5)
    assert metrics["false_positives"] == 1
    assert metrics["false_negatives"] == 1


def test_best_threshold_by_f1_returns_valid_probability():
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, size=200)
    y_proba = rng.random(200)
    threshold = best_threshold_by_f1(y_true, y_proba)
    assert 0.0 <= threshold <= 1.0
