"""
Project Manifest Package for VideoAgent.
"""
from agents.video.manifest.schemas import (
    EditableVideoProjectManifest,
    ProjectAsset,
    ProjectAudioAsset,
    ProjectSubtitleAsset,
    TimelineClip,
    ProjectTimeline,
    RenderOutputRecord,
    ProjectValidationReport,
    ProjectChangeRecord,
    ProjectChangeOperation,
    ProjectLifecycleStatus,
    DependencyStatus
)
from agents.video.manifest.service import ProjectManifestService, ManifestMigrationRegistry
from agents.video.manifest.regeneration import (
    SceneRegenerationService,
    SceneRegenerationRequest,
    SceneRegenerationResult
)
