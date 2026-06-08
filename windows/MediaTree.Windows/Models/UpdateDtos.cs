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
}

public sealed class UpdateCheckResultDto
{
    [JsonPropertyName("current_version")]
    public string CurrentVersion { get; set; } = "";

    [JsonPropertyName("has_update")]
    public bool HasUpdate { get; set; }

    [JsonPropertyName("versions")]
    public List<VersionEntryDto> Versions { get; set; } = [];
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

    [JsonPropertyName("requires_windows_base_update")]
    public bool RequiresWindowsBaseUpdate { get; set; }

    [JsonPropertyName("windows_reason")]
    public string WindowsReason { get; set; } = "";
}

