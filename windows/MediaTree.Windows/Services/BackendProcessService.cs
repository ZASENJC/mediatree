using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;

namespace MediaTree.Windows.Services;

public sealed class BackendProcessService : IDisposable
{
    private readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(2) };
    private Process? _process;
    private int _port;
    private BackendAccessSettings _accessSettings = new();

    public Uri BackendUri => new($"http://127.0.0.1:{_port}/");
    public BackendAccessSettings AccessSettings => _accessSettings;

    public async Task<Uri> StartAsync(CancellationToken cancellationToken = default)
    {
        AppPaths.EnsureRuntimeDirectories();
        if (!File.Exists(AppPaths.ServerExe))
        {
            throw new FileNotFoundException("Cannot find bundled backend executable.", AppPaths.ServerExe);
        }

        _accessSettings = BackendAccessSettingsStore.Load();
        _port = _accessSettings.EffectivePort(PortAllocator.GetFreeLoopbackPort());
        var stdoutLog = Path.Combine(AppPaths.LogsDirectory, "backend.stdout.log");
        var stderrLog = Path.Combine(AppPaths.LogsDirectory, "backend.stderr.log");

        var startInfo = new ProcessStartInfo
        {
            FileName = AppPaths.ServerExe,
            Arguments = $"--host {_accessSettings.BindHost} --port {_port} --data-dir \"{AppPaths.DataDirectory}\" --media-root \"{AppPaths.MediaDirectory}\"",
            WorkingDirectory = AppPaths.ServerDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        startInfo.Environment["MEDIATREE_RUNTIME"] = "windows";
        startInfo.Environment["MEDIATREE_UPDATE_PLATFORM"] = "windows";

        ShellLogger.Info($"Starting backend ({_accessSettings.AccessModeLabel}): {AppPaths.ServerExe} {startInfo.Arguments}");
        _process = Process.Start(startInfo) ?? throw new InvalidOperationException("Failed to start backend process.");
        _ = Task.Run(() => PipeToFileAsync(_process.StandardOutput, stdoutLog, cancellationToken), cancellationToken);
        _ = Task.Run(() => PipeToFileAsync(_process.StandardError, stderrLog, cancellationToken), cancellationToken);

        await WaitForHealthAsync(cancellationToken);
        return BackendUri;
    }

    public async Task<Uri> RestartAsync()
    {
        Stop();
        return await StartAsync();
    }

    public string RemoteAccessUrl => _accessSettings.DisplayUrl(GetPreferredLanAddress());

    public static string GetPreferredLanAddress()
    {
        try
        {
            foreach (var networkInterface in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (networkInterface.OperationalStatus != OperationalStatus.Up)
                {
                    continue;
                }

                if (networkInterface.NetworkInterfaceType is NetworkInterfaceType.Loopback or NetworkInterfaceType.Tunnel)
                {
                    continue;
                }

                foreach (var address in networkInterface.GetIPProperties().UnicastAddresses)
                {
                    if (address.Address.AddressFamily != AddressFamily.InterNetwork)
                    {
                        continue;
                    }

                    var value = address.Address.ToString();
                    if (!value.StartsWith("169.254.", StringComparison.Ordinal))
                    {
                        return value;
                    }
                }
            }
        }
        catch
        {
            // Best-effort display helper for Settings.
        }

        return "";
    }

    private async Task WaitForHealthAsync(CancellationToken cancellationToken)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(60);
        while (DateTimeOffset.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (_process?.HasExited == true)
            {
                ShellLogger.Error($"Backend exited with code {_process.ExitCode}.");
                throw new InvalidOperationException($"Backend exited with code {_process.ExitCode}.");
            }

            try
            {
                using var response = await _httpClient.GetAsync(new Uri(BackendUri, "api/health"), cancellationToken);
                if (response.IsSuccessStatusCode)
                {
                    ShellLogger.Info($"Backend is healthy at {BackendUri}.");
                    return;
                }
            }
            catch
            {
                await Task.Delay(500, cancellationToken);
            }
        }

        throw new TimeoutException("Backend did not become healthy within 60 seconds.");
    }

    public static async Task PipeToFileAsync(StreamReader reader, string path, CancellationToken cancellationToken = default)
    {
        await using var file = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.ReadWrite);
        await using var writer = new StreamWriter(file) { AutoFlush = true };
        while (!cancellationToken.IsCancellationRequested)
        {
            var line = await reader.ReadLineAsync();
            if (line is null)
            {
                break;
            }

            if (line.Length > 0)
            {
                await writer.WriteLineAsync(line);
            }
        }
    }

    public void Stop()
    {
        try
        {
            if (_process is { HasExited: false })
            {
                _process.Kill(entireProcessTree: true);
                _process.WaitForExit(5000);
            }
        }
        catch
        {
            // Best-effort cleanup on app exit.
        }
    }

    public void Dispose()
    {
        Stop();
        _httpClient.Dispose();
        _process?.Dispose();
    }
}
