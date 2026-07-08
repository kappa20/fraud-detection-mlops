"""Métriques et visualisations d'évaluation pour la classification de
fraude, un problème fortement déséquilibré (492 fraudes / 284 807
transactions, soit 0,17 %). L'accuracy est volontairement écartée comme
métrique de décision : un modèle qui prédit toujours "légitime" obtient
déjà 99,83 % d'accuracy sans détecter la moindre fraude. Le **PR-AUC**
(average precision) est retenu comme métrique primaire (Livrable 5/6).
"""

from pathlib import Path
from typing import Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(y_true, y_proba, threshold: float = 0.5) -> Dict[str, float]:
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "pr_auc": float(average_precision_score(y_true, y_proba)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "threshold": float(threshold),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
    }


def best_threshold_by_f1(y_true, y_proba) -> float:
    """Choisit le seuil de décision qui maximise le F1-score sur le jeu
    fourni, plutôt que le seuil par défaut 0.5, arbitraire face à un fort
    déséquilibre de classes."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_proba)
    if len(thresholds) == 0:
        return 0.5
    f1_scores = 2 * precision * recall / (precision + recall + 1e-12)
    best_idx = int(np.argmax(f1_scores[:-1]))
    return float(thresholds[best_idx])


def plot_confusion_matrix(y_true, y_proba, threshold: float, out_path: Path) -> None:
    y_pred = (y_proba >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(4, 4))
    im = ax.imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Légitime", "Fraude"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Légitime", "Fraude"])
    ax.set_xlabel("Prédit")
    ax.set_ylabel("Réel")
    ax.set_title(f"Matrice de confusion (seuil={threshold:.3f})")
    fig.colorbar(im)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_precision_recall_curve(y_true, y_proba, out_path: Path) -> None:
    precision, recall, _ = precision_recall_curve(y_true, y_proba)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(recall, precision)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Courbe Precision-Recall")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
