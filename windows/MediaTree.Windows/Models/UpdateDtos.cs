using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace MediaTree.Windows.Models;

public sealed class VersionInfoDto
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("runtime_version")]
    public string RuntimeVersion { get; set; } = "";

    [JsonPropertyName("current_source")]
    public string CurrentSource { get; set; } = "";

    [JsonPropertyName("base_version")]
    public string BaseVersion { get; set; } = "";

    [JsonPropertyName("effective_version")]
    public string EffectiveVersion { get; set; } = "";

    [JsonPropertyName("status_note")]
    public string StatusNote { get; set; } = "";
}

public sealed class UpdateCheckResultDto
{
    [JsonPropertyName("current_version")]
    public string CurrentVersion { get; set; } = "";

    [JsonPropertyName("runtime_version")]
    public string RuntimeVersion { get; set; } = "";

    [JsonPropertyName("current_source")]
    public string CurrentSource { get; set; } = "";

    [JsonPropertyName("base_version")]
    public string BaseVersion { get; set; } = "";

    [JsonPropertyName("effective_version")]
    public string EffectiveVersion { get; set; } = "";

    [JsonPropertyName("status_note")]
    public string StatusNote { get; set; } = "";

    [JsonPropertyName("has_update")]
    public bool HasUpdate { get; set; }

    [JsonPropertyName("dockerhub_latest")]
    public DockerHubLatestBaselineDto? DockerHubLatest { get; set; }

    [JsonPropertyName("latest_sync_warning")]
    public LatestSyncWarningDto? LatestSyncWarning { get; set; }

    [JsonPropertyName("versions")]
    public List<VersionEntryDto> Versions { get; set; } = [];
}

public sealed class DockerHubLatestBaselineDto
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("display_version")]
    public string DisplayVersion { get; set; } = "";

    [JsonPropertyName("published_at")]
    public string PublishedAt { get; set; } = "";

    [JsonPropertyName("html_url")]
    public string HtmlUrl { get; set; } = "";

    [JsonPropertyName("source")]
    public string Source { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";
}

public sealed class LatestSyncWarningDto
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("severity")]
    public string Severity { get; set; } = "";

    [JsonPropertyName("release_version")]
    public string ReleaseVersion { get; set; } = "";

    [JsonPropertyName("release_display_version")]
    public string ReleaseDisplayVersion { get; set; } = "";

    [JsonPropertyName("release_published_at")]
    public string ReleasePublishedAt { get; set; } = "";

    [JsonPropertyName("dockerhub_latest_version")]
    public string DockerHubLatestVersion { get; set; } = "";

    [JsonPropertyName("dockerhub_latest_updated_at")]
    public string DockerHubLatestUpdatedAt { get; set; } = "";

    [JsonPropertyName("evidence")]
    public string Evidence { get; set; } = "";

    [JsonPropertyName("message")]
    public string Message { get; set; } = "";

    [JsonPropertyName("action")]
    public string Action { get; set; } = "";
}

public sealed class VersionEntryDto
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("display_version")]
    public string DisplayVersion { get; set; } = "";

    [JsonPropertyName("published_at")]
    public DateTimeOffset PublishedAt { get; set; }

    [JsonPropertyName("update_type")]
    public string UpdateType { get; set; } = "";

    [JsonPropertyName("html_url")]
    public string HtmlUrl { get; set; } = "";

    [JsonPropertyName("size")]
    public long Size { get; set; }

    [JsonPropertyName("requires_image_update")]
    public bool RequiresImageUpdate { get; set; }

    [JsonPropertyName("requires_windows_base_update")]
    public bool RequiresWindowsBaseUpdate { get; set; }

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";

    [JsonPropertyName("windows_reason")]
    public string WindowsReason { get; set; } = "";
}

public sealed class UpdateStatusDto
{
    [JsonPropertyName("status")]
    public string Status { get; set; } = "idle";

    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("downloaded")]
    public long Downloaded { get; set; }

    [JsonPropertyName("total")]
    public long Total { get; set; }

    [JsonPropertyName("message")]
    public string Message { get; set; } = "";

    [JsonPropertyName("update_type")]
    public string UpdateType { get; set; } = "";

    [JsonPropertyName("logs")]
    public List<string> Logs { get; set; } = [];

    [JsonPropertyName("can_rollback")]
    public bool CanRollback { get; set; }

    [JsonPropertyName("rollback_version")]
    public string RollbackVersion { get; set; } = "";
}

public sealed class UpdateActionResultDto
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; } = true;

    [JsonPropertyName("message")]
    public string Message { get; set; } = "";

    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("error")]
    public string Error { get; set; } = "";
}

public sealed class ChangelogDto
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("body")]
    public string Body { get; set; } = "";
}
