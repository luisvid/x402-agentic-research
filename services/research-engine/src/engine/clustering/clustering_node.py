"""
ClusteringNode: Groups related news articles into clusters.

Copied from parent project with import path fixed:
  from utils.model_manager -> from engine.utils.model_manager
"""

import logging
import re
from typing import Any, Dict, List

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

from ..utils.model_manager import model_manager

logger = logging.getLogger(__name__)


class ClusteringNode:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", similarity_threshold: float = 0.70):
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.model = model_manager.get_sentence_transformer(model_name)

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()[:512]

    def _extract_clustering_features(self, article: Dict[str, Any]) -> str:
        features = []
        if article.get("title"):
            features.append(f"TITLE: {self._clean_text(article['title'])}")
        if article.get("content"):
            content = self._clean_text(article["content"])[:200]
            if content:
                features.append(f"CONTENT: {content}")
        return " ".join(features)

    def cluster_articles(
        self, articles: List[Dict[str, Any]], min_cluster_size: int = 2, max_cluster_size: int = 10
    ) -> List[Dict[str, Any]]:
        if len(articles) < min_cluster_size:
            return [
                {
                    "cluster_id": 0,
                    "articles": articles,
                    "cluster_size": len(articles),
                    "representative_title": articles[0].get("title", "Unknown") if articles else "Empty",
                    "urls": [a.get("url") for a in articles if a.get("url")],
                }
            ]

        texts = [self._extract_clustering_features(a) for a in articles]
        embeddings = self.model.encode(texts)
        similarity_matrix = cosine_similarity(embeddings)
        distance_matrix = np.clip(1 - similarity_matrix, 0, 2)

        clustering = DBSCAN(
            eps=1 - self.similarity_threshold, min_samples=min_cluster_size, metric="precomputed"
        ).fit(distance_matrix)

        clusters: Dict[int, list] = {}
        noise_articles = []

        for idx, label in enumerate(clustering.labels_):
            if label == -1:
                noise_articles.append(articles[idx])
            else:
                clusters.setdefault(label, []).append(articles[idx])

        result_clusters = []

        for cluster_id, cluster_articles in clusters.items():
            if len(cluster_articles) > max_cluster_size:
                cluster_articles = cluster_articles[:max_cluster_size]

            titles = [a.get("title", "") for a in cluster_articles]
            representative_title = self._get_representative_title(titles)

            result_clusters.append(
                {
                    "cluster_id": int(cluster_id),
                    "articles": cluster_articles,
                    "cluster_size": len(cluster_articles),
                    "representative_title": representative_title,
                    "urls": [a.get("url") for a in cluster_articles if a.get("url")],
                    "buzz_score": len(cluster_articles),
                }
            )

        for idx, article in enumerate(noise_articles):
            result_clusters.append(
                {
                    "cluster_id": f"noise_{idx}",
                    "articles": [article],
                    "cluster_size": 1,
                    "representative_title": article.get("title", "Unknown"),
                    "urls": [article.get("url")] if article.get("url") else [],
                    "buzz_score": 1,
                }
            )

        result_clusters.sort(key=lambda x: x["buzz_score"], reverse=True)
        return result_clusters

    def _get_representative_title(self, titles: List[str]) -> str:
        valid_titles = [t for t in titles if t and t.strip()]
        if not valid_titles:
            return "Unknown Event"
        representative = max(valid_titles, key=len)
        representative = self._clean_text(representative)
        if len(representative) > 100:
            representative = representative[:97] + "..."
        return representative
