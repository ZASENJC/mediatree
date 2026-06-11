using System;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MediaTree.Windows.Platform;

public sealed class BackendAccessSettings
{
    public const int DefaultRemotePort = 27581;
    private const int MinUserPort = 1024;
    private const int MaxUserPort = 65535;

    [JsonPropertyName("allowRemoteAccess")]
    public bool AllowRemoteAccess { get; set; }

    [JsonPropertyName("remotePort")]
    public int RemotePort { get; set; } = DefaultRemotePort;

    [JsonIgnore]
    public string BindHost => AllowRemoteAccess ? "0.0.0.0" : "127.0.0.1";

    [JsonIgnore]
    public string AccessModeLabel => AllowRemoteAccess ? "局域网访问" : "本机访问";

    public int EffectivePort(int loopbackPort)
        => AllowRemoteAccess ? NormalizePort(RemotePort) : loopbackPort;

    public string DisplayUrl(string host)
    {
        var displayHost = string.IsNullOrWhiteSpace(host) ? "此电脑IP" : host.Trim();
        return $"http://{displayHost}:{NormalizePort(RemotePort)}";
    }

    public static int NormalizePort(int port)
        => port is >= MinUserPort and <= MaxUserPort ? port : DefaultRemotePort;
}

public static class BackendAccessSettingsStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
    };

    public static BackendAccessSettings Load()
        => Load(SettingsFilePath);

    public static BackendAccessSettings Load(string filePath)
    {
        try
        {
            if (!File.Exists(filePath))
            {
                return new BackendAccessSettings();
            }

            var json = File.ReadAllText(filePath);
            var settings = JsonSerializer.Deserialize<BackendAccessSettings>(json) ?? new BackendAccessSettings();
            settings.RemotePort = BackendAccessSettings.NormalizePort(settings.RemotePort);
            return settings;
        }
        catch
        {
            return new BackendAccessSettings();
        }
    }

    public static void Save(BackendAccessSettings settings)
        => Save(settings, SettingsFilePath);

    public static void Save(BackendAccessSettings settings, string filePath)
    {
        settings.RemotePort = BackendAccessSettings.NormalizePort(settings.RemotePort);
        var directory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(filePath, JsonSerializer.Serialize(settings, JsonOptions));
    }

    private static string SettingsFilePath => Path.Combine(AppPaths.WindowsStateDirectory, "backend-access.json");
}
