using System;
using System.Diagnostics;
using System.Threading.Tasks;
using Microsoft.UI.Xaml;
using Microsoft.Web.WebView2.Core;
using MediaTree.Windows.Services;

namespace MediaTree.Windows;

public sealed partial class MainWindow : Window
{
    private readonly BackendProcessService _backend = new();
    private Uri? _backendUri;

    public MainWindow()
    {
        InitializeComponent();
        Closed += OnClosed;
        _ = StartAsync();
    }

    private async Task StartAsync()
    {
        try
        {
            StatusText.Text = "启动本地后端";
            _backendUri = await _backend.StartAsync();
            StatusText.Text = "初始化 WebView2";
            await Browser.EnsureCoreWebView2Async();
            ConfigureWebView();
            LoadingOverlay.Visibility = Visibility.Collapsed;
            Browser.Source = _backendUri;
        }
        catch (Exception ex)
        {
            StatusText.Text = "启动失败，正在打开日志目录";
            Debug.WriteLine(ex);
            AppPaths.EnsureLogsDirectory();
            Process.Start(new ProcessStartInfo
            {
                FileName = AppPaths.LogsDirectory,
                UseShellExecute = true,
            });
        }
    }

    private void ConfigureWebView()
    {
        if (Browser.CoreWebView2 == null || _backendUri == null)
        {
            return;
        }

        Browser.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
        Browser.CoreWebView2.Settings.AreDevToolsEnabled = true;
        Browser.CoreWebView2.NavigationStarting += (_, args) =>
        {
            if (!NavigationGuard.IsAllowed(args.Uri, _backendUri))
            {
                args.Cancel = true;
                Process.Start(new ProcessStartInfo
                {
                    FileName = args.Uri,
                    UseShellExecute = true,
                });
            }
        };
        Browser.CoreWebView2.AddHostObjectToScript("mediaTreeWindows", new WindowsBridge(_backend));
        _ = Browser.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(
            "window.mediaTreeWindows = chrome.webview.hostObjects.mediaTreeWindows;");
    }

    private void OnClosed(object sender, WindowEventArgs args)
    {
        _backend.Dispose();
    }
}
