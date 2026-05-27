"""Application adapters for creative and productivity software."""

from .photoshop_adapter import PhotoshopAdapter
from .illustrator_adapter import IllustratorAdapter
from .aftereffects_adapter import AfterEffectsAdapter
from .autocad_adapter import AutoCADAdapter
from .blender_adapter import BlenderAdapter
from .office_adapter import OfficeAdapter
from .github_service import GitHubService, get_github_service
from .credential_store import CredentialStore, get_credential_store
from .email_service import EmailService, get_email_service, PROVIDERS as EMAIL_PROVIDERS
from .crm_service import CRMService, get_crm_service, STAGES as CRM_STAGES, CATEGORIES as CRM_CATEGORIES

__all__ = [
    "PhotoshopAdapter",
    "IllustratorAdapter",
    "AfterEffectsAdapter",
    "AutoCADAdapter",
    "BlenderAdapter",
    "OfficeAdapter",
    "GitHubService",
    "get_github_service",
    "CredentialStore",
    "get_credential_store",
    "EmailService",
    "get_email_service",
    "EMAIL_PROVIDERS",
    "CRMService",
    "get_crm_service",
    "CRM_STAGES",
    "CRM_CATEGORIES",
]
