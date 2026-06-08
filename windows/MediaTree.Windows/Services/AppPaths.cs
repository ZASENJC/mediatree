using System;
using System.IO;

namespace MediaTree.Windows.Services;

public static class AppPaths
{
    public static string AppDirectory => AppContext.BaseDirectory;
    public static string ServerDirectory => Path.Combine(AppDirectory, "server");
    public static string ServerExe => Path.Combine(ServerDirectory, "mediatree-server.exe");
    public static string MpvDirectory => Path.Combine(AppDirectory, "mpv");
    public static string MpvExe => Path.Combine(MpvDirectory, "mpv.exe");
    public static string DataDirectory => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "MediaTree",
        "data");
    public static string MediaDirectory => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "MediaTree",
        "media");
    public static string LogsDirectory => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "MediaTree",
        "logs");
    public static string WebView2Directory => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "MediaTree",
        "webview2");

    public static void EnsureRuntimeDirectories()
    {
        Directory.CreateDirectory(DataDirectory);
        Directory.CreateDirectory(MediaDirectory);
        Directory.CreateDirectory(WebView2Directory);
        EnsureLogsDirectory();
    }

    public static void EnsureLogsDirectory()
    {
        Directory.CreateDirectory(LogsDirectory);
    }
}
