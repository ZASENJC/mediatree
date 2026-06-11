using System.IO;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MediaTree.Windows.Platform;

public sealed class UiPreferenceState
{
    [JsonPropertyName("hideHomeTitleText")]
    public bool HideHomeTitleText { get; set; }

    [JsonPropertyName("showSourceName")]
    public bool ShowSourceName { get; set; }

    [JsonPropertyName("excludedFolders")]
    public List<string> ExcludedFolders { get; set; } = [];
}

public static class UiPreferenceStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
    };

    public static UiPreferenceState Load()
        => Load(PreferencesFilePath);

    public static UiPreferenceState Load(string filePath)
    {
        try
        {
            if (!File.Exists(filePath))
            {
                return new UiPreferenceState();
            }

            var json = File.ReadAllText(filePath);
            return JsonSerializer.Deserialize<UiPreferenceState>(json) ?? new UiPreferenceState();
        }
        catch
        {
            return new UiPreferenceState();
        }
    }

    public static void Save(UiPreferenceState state)
        => Save(state, PreferencesFilePath);

    public static void Save(UiPreferenceState state, string filePath)
    {
        var directory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(filePath, JsonSerializer.Serialize(state, JsonOptions));
    }

    private static string PreferencesFilePath => Path.Combine(AppPaths.WindowsStateDirectory, "ui-prefs.json");
}
