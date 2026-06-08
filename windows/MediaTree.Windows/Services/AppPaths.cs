using System;
using System.IO;

namespace MediaTree.Windows.Services;

public static class AppPaths
{
    public static string AppDirectory => AppContext.BaseDirectory;
    public static string ServerDirectory => Path.Combine(AppDirectory, "server");
    public static string ServerExe => Path.Combine(ServerDirectory, "mediatree-server.exe");
    public static string MpvDirectory => Path.Combine(AppDirectory, "mpv");
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
    public static string WindowsStateDirectory => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "MediaTree",
        "windows");
    public static string WindowsSessionFile => Path.Combine(WindowsStateDirectory, "session.dpapi.json");

    public static void EnsureRuntimeDirectories()
    {
        Directory.CreateDirectory(DataDirectory);
        Directory.CreateDirectory(MediaDirectory);
        Directory.CreateDirectory(WindowsStateDirectory);
        EnsureLogsDirectory();
    }

    public static void EnsureLogsDirectory()
    {
        Directory.CreateDirectory(LogsDirectory);
    }
}
