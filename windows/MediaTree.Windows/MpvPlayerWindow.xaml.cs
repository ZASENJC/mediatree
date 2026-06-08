using System;
using System.Diagnostics;
using System.IO;
using Microsoft.UI.Xaml;
using WinRT.Interop;
using MediaTree.Windows.Services;

namespace MediaTree.Windows;

public sealed partial class MpvPlayerWindow : Window
{
    private readonly string _url;
    private Process? _process;
    private bool _started;

    public MpvPlayerWindow(string url)
    {
        _url = url;
        InitializeComponent();
        Closed += OnClosed;
        Activated += OnActivated;
    }

    private void OnActivated(object sender, WindowActivatedEventArgs args)
    {
        if (_started)
        {
            return;
        }

        _started = true;
        StartMpv();
    }

    private void StartMpv()
    {
        if (!File.Exists(AppPaths.MpvExe))
        {
            StatusText.Text = "未找到内置 mpv.exe，请重新构建 Windows 包。";
            ShellLogger.Error($"Bundled mpv.exe was not found: {AppPaths.MpvExe}");
            return;
        }

        var hwnd = WindowNative.GetWindowHandle(this);
        if (hwnd == IntPtr.Zero)
        {
            StatusText.Text = "播放器窗口句柄不可用。";
            ShellLogger.Error("MPV host window handle is zero.");
            return;
        }

        var stdoutLog = Path.Combine(AppPaths.LogsDirectory, "mpv.stdout.log");
        var stderrLog = Path.Combine(AppPaths.LogsDirectory, "mpv.stderr.log");
        var startInfo = new ProcessStartInfo
        {
            FileName = AppPaths.MpvExe,
            WorkingDirectory = AppPaths.MpvDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        startInfo.ArgumentList.Add($"--wid={hwnd}");
        startInfo.ArgumentList.Add("--force-window=yes");
        startInfo.ArgumentList.Add("--idle=no");
        startInfo.ArgumentList.Add("--keep-open=no");
        startInfo.ArgumentList.Add("--no-terminal");
        startInfo.ArgumentList.Add(_url);

        try
        {
            ShellLogger.Info($"Starting bundled mpv: {AppPaths.MpvExe} --wid={hwnd}");
            _process = Process.Start(startInfo);
            if (_process == null)
            {
                StatusText.Text = "启动 MPV 失败。";
                ShellLogger.Error("Process.Start returned null for mpv.");
                return;
            }

            StatusText.Text = "";
            _ = BackendProcessService.PipeToFileAsync(_process.StandardOutput, stdoutLog);
            _ = BackendProcessService.PipeToFileAsync(_process.StandardError, stderrLog);
        }
        catch (Exception ex)
        {
            StatusText.Text = "启动 MPV 失败，已写入日志。";
            ShellLogger.Error(ex, "Failed to start bundled mpv.");
        }
    }

    private void OnClosed(object sender, WindowEventArgs args)
    {
        try
        {
            if (_process is { HasExited: false })
            {
                _process.Kill(entireProcessTree: true);
                _process.WaitForExit(3000);
            }
        }
        catch
        {
            // Best-effort cleanup on player window close.
        }
        finally
        {
            _process?.Dispose();
            _process = null;
        }
    }
}
