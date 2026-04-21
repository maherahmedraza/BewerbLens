# ╔══════════════════════════════════════════════════════════════╗
# ║  Classifier Factory — Provider selection                     ║
# ║  Loads the appropriate classifier implementation based on    ║
# ║  the CLASSIFIER_PROVIDER setting.                            ║
# ╚══════════════════════════════════════════════════════════════╝

from classifier_base import EmailClassifier
from config import settings


def get_classifier() -> EmailClassifier:
    """
    Retorna una instancia del clasificador configurado.
    Permite cambiar entre Gemini y otros modelos fácilmente.
    """
    provider = settings.classifier_provider.lower()

    if provider == "gemini":
        from gemini_classifier import GeminiClassifier
        return GeminiClassifier()

    # Placeholder para futuros modelos:
    # elif provider == "openai":
    #     from openai_classifier import OpenAIClassifier
    #     return OpenAIClassifier()

    raise ValueError(f"Proveedor de clasificación no soportado: {provider}")
