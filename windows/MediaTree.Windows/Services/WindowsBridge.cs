using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading.Tasks;

namespace MediaTree.Windows.Services;

[ClassInterface(ClassInterfaceType.AutoDual)]
[ComVisible(true)]
public sealed class WindowsBridge
{
    private readonly BackendProcessService _backend;

    public WindowsBridge(BackendProcessService backend)
    {
        _backend = backend;
    }

    public string GetShellInfo()
    {
        return "{\"version\":\"1\",\"runtime\":\"windows\"}";
    }

    public string PickFolder()
    {
        return "";
    }

    public void OpenLogs()
    {
        AppPaths.EnsureLogsDirectory();
        Process.Start(new ProcessStartInfo
        {
            FileName = AppPaths.LogsDirectory,
            UseShellExecute = true,
        });
    }

    public async Task RestartBackend()
    {
        await _backend.RestartAsync();
    }
}
