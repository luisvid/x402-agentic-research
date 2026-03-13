"""
Model Manager: Singleton to manage ML model instances and avoid reloading.
"""

import logging
from typing import Optional

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class ModelManager:
    _instance: Optional["ModelManager"] = None
    _sentence_transformer: Optional[SentenceTransformer] = None

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_sentence_transformer(self, model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
        if self._sentence_transformer is None:
            logger.info(f"Loading sentence transformer model: {model_name}")
            self._sentence_transformer = SentenceTransformer(model_name)
            logger.info(f"Model loaded: {model_name}")
        return self._sentence_transformer


model_manager = ModelManager()
