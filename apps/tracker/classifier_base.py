# ╔══════════════════════════════════════════════════════════════╗
# ║  Classifier Base — Abstraction for AI models                 ║
# ║  Defines the common protocol for all classification          ║
# ║  implementations (Gemini, OpenAI, etc).                      ║
# ╚══════════════════════════════════════════════════════════════╝

from typing import Protocol, runtime_checkable
from models import EmailMetadata, EmailClassification


@runtime_checkable
class EmailClassifier(Protocol):
    """
    Protocolo que define la interfaz para clasificadores de email.
    Permite intercambiar proveedores de IA (Gemini, OpenAI, etc) sin 
    modificar la lógica de la pipeline.
    """

    def classify(self, emails: list[EmailMetadata]) -> list[EmailClassification]:
        """
        Clasifica una lista de emails.
        Debe manejar el loteado (batching) internamente si el modelo lo requiere.
        """
        ...

    @property
    def provider_name(self) -> str:
        """Nombre del proveedor (ej. 'gemini', 'openai')."""
        ...
