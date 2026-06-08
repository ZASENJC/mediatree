using System;
using System.IO;

namespace MediaTree.Windows.Services;

public static class ShellLogger
{
    private static readonly object Sync = new();

    public static string LogFile => Path.Combine(AppPaths.LogsDirectory, "shell.log");

    public static void Info(string message)
    {
        Write("INFO", message);
    }

    public static void Error(Exception exception, string message)
    {
        Write("ERROR", $"{message}{Environment.NewLine}{exception}");
    }

    public static void Error(string message)
    {
        Write("ERROR", message);
    }

    private static void Write(string level, string message)
    {
        try
        {
            AppPaths.EnsureLogsDirectory();
            var line = $"{DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss.fff zzz} [{level}] {message}{Environment.NewLine}";
            lock (Sync)
            {
                File.AppendAllText(LogFile, line);
            }
        }
        catch
        {
            // Logging must never prevent app startup or shutdown.
        }
    }
}
