using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.Web.WebView2.Core;
using Windows.Storage;
using Windows.Storage.Pickers;
using WinRT.Interop;
using MediaTree.Windows.Services;

namespace MediaTree.Windows;

public sealed partial class MainWindow : Window
{
    private readonly BackendProcessService _backend = new();
    private readonly Grid _browserHost;
    private readonly Grid _loadingOverlay;
    private readonly TextBlock _statusText;
    private readonly StackPanel _actionsPanel;
    private Uri? _backendUri;
    private WebView2? _browser;
    private bool _startupStarted;

    public MainWindow()
    {
        ShellLogger.Info("Creating main window.");
        Title = "MediaTree";
        (_browserHost, _loadingOverlay, _statusText, _actionsPanel) = BuildContent();
        Closed += OnClosed;
    }

    public void ShowAndBringToFront()
    {
        Activate();

        var hwnd = WindowNative.GetWindowHandle(this);
        ShellLogger.Info($"Main window activated. HWND=0x{hwnd.ToInt64():X}.");
    }

    private (Grid browserHost, Grid loadingOverlay, TextBlock statusText, StackPanel actionsPanel) BuildContent()
    {
        var root = new Grid
        {
            Background = new Microsoft.UI.Xaml.Media.SolidColorBrush(Colors.Black),
        };
        root.Loaded += OnRootLoaded;

        var browserHost = new Grid();
        root.Children.Add(browserHost);

        var loadingOverlay = new Grid
        {
            Background = new Microsoft.UI.Xaml.Media.SolidColorBrush(Colors.Black),
            Visibility = Visibility.Visible,
        };
        var stack = new StackPanel
        {
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Spacing = 16,
        };
        stack.Children.Add(new TextBlock
        {
            Text = "正在启动 MediaTree...",
            Foreground = new Microsoft.UI.Xaml.Media.SolidColorBrush(Colors.White),
            FontSize = 16,
            HorizontalAlignment = HorizontalAlignment.Center,
        });
        var statusText = new TextBlock
        {
            Text = "准备本地后端",
            Foreground = new Microsoft.UI.Xaml.Media.SolidColorBrush(ColorHelper.FromArgb(0xFF, 0xB8, 0xC7, 0xD9)),
            FontSize = 12,
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        stack.Children.Add(statusText);

        var actionsPanel = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Center,
            Spacing = 10,
            Visibility = Visibility.Collapsed,
        };
        stack.Children.Add(actionsPanel);

        loadingOverlay.Children.Add(stack);
        root.Children.Add(loadingOverlay);
        Content = root;

        return (browserHost, loadingOverlay, statusText, actionsPanel);
    }

    private void OnRootLoaded(object sender, RoutedEventArgs args)
    {
        ShellLogger.Info("Main window content loaded.");
        BeginStartup();
    }

    private void BeginStartup()
    {
        if (_startupStarted)
        {
            return;
        }

        _startupStarted = true;
        ShellLogger.Info("Queueing runtime startup pipeline.");
        DispatcherQueue.TryEnqueue(() => _ = StartAsync());
    }

    private async Task StartAsync()
    {
        try
        {
            ShellLogger.Info("Runtime startup pipeline started.");
            _statusText.Text = "启动本地后端";
            _backendUri = await _backend.StartAsync();
            ShellLogger.Info($"Backend startup completed: {_backendUri}.");
            _statusText.Text = "初始化 WebView2";
            var browser = CreateBrowser();
            await InitializeWebViewAsync(browser);
            ShellLogger.Info("WebView2 core initialized.");
            await ConfigureWebViewAsync(browser);
            _loadingOverlay.Visibility = Visibility.Collapsed;
            browser.Source = _backendUri;
            ShellLogger.Info($"WebView2 navigating to {_backendUri}.");
        }
        catch (Exception ex)
        {
            Debug.WriteLine(ex);
            ShellLogger.Error(ex, "Main window startup failed.");
            ShowStartupFailure(ex);
        }
    }

    private WebView2 CreateBrowser()
    {
        if (_browser != null)
        {
            return _browser;
        }

        _browser = new WebView2
        {
            HorizontalAlignment = HorizontalAlignment.Stretch,
            VerticalAlignment = VerticalAlignment.Stretch,
        };
        _browserHost.Children.Insert(0, _browser);
        return _browser;
    }

    private static async Task InitializeWebViewAsync(WebView2 browser)
    {
        browser.CoreWebView2Initialized += (_, args) =>
        {
            if (args.Exception != null)
            {
                ShellLogger.Error(args.Exception, "WebView2 initialization event failed.");
                return;
            }

            ShellLogger.Info("WebView2 initialization event completed.");
        };

        Directory.CreateDirectory(AppPaths.WebView2Directory);
        Environment.SetEnvironmentVariable("WEBVIEW2_USER_DATA_FOLDER", AppPaths.WebView2Directory);
        Environment.SetEnvironmentVariable("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--disable-gpu --disable-gpu-compositing");
        ShellLogger.Info($"Ensuring WebView2 core. UserDataFolder={AppPaths.WebView2Directory}");
        var initializeTask = browser.EnsureCoreWebView2Async().AsTask();
        var completed = await Task.WhenAny(initializeTask, Task.Delay(TimeSpan.FromSeconds(30)));
        if (completed != initializeTask)
        {
            throw new TimeoutException("WebView2 初始化超过 30 秒。请检查 WebView2 Runtime，或先用外部浏览器打开本地页面。");
        }

        await initializeTask;
    }

    private async Task ConfigureWebViewAsync(WebView2 browser)
    {
        if (browser.CoreWebView2 == null || _backendUri == null)
        {
            return;
        }

        browser.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
        browser.CoreWebView2.Settings.AreDevToolsEnabled = true;
        browser.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
        browser.CoreWebView2.NavigationCompleted += (sender, args) =>
        {
            ShellLogger.Info($"WebView2 navigation completed. Success={args.IsSuccess}; Error={args.WebErrorStatus}.");
            _ = LogPageStateWithDelayAsync(browser, IsDiagnosticsEnabled());
        };
        browser.CoreWebView2.NavigationStarting += (_, args) =>
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
        const string bridgeScript = """
            (() => {
              const post = (message) => {
                if (window.chrome && window.chrome.webview) {
                  window.chrome.webview.postMessage(message);
                }
              };
              window.mediaTreeWindows = { postMessage: post };
              window.addEventListener('error', (event) => {
                post({
                  action: 'logClientError',
                  message: event.message || 'Window error',
                  source: event.filename || '',
                  line: event.lineno || 0,
                  column: event.colno || 0
                });
              });
              window.addEventListener('unhandledrejection', (event) => {
                const reason = event.reason;
                post({
                  action: 'logClientError',
                  message: reason && reason.message ? reason.message : String(reason || 'Unhandled rejection'),
                  source: 'unhandledrejection',
                  line: 0,
                  column: 0
                });
              });
            })();
            """;
        await browser.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(bridgeScript).AsTask();
    }

    private static bool IsDiagnosticsEnabled()
    {
        return string.Equals(
            Environment.GetEnvironmentVariable("MEDIATREE_WINDOWS_DIAGNOSTICS"),
            "1",
            StringComparison.Ordinal);
    }

    private static async Task LogPageStateWithDelayAsync(WebView2 browser, bool capturePreview)
    {
        await LogPageStateAsync(browser, "immediate", capturePreview);
        await Task.Delay(TimeSpan.FromSeconds(2));
        await LogPageStateAsync(browser, "after-2s", capturePreview);
        await Task.Delay(TimeSpan.FromSeconds(8));
        await LogPageStateAsync(browser, "after-10s", capturePreview);
    }

    private static async Task LogPageStateAsync(WebView2 browser, string phase, bool capturePreview)
    {
        try
        {
            if (browser.CoreWebView2 == null)
            {
                return;
            }

            var result = await browser.CoreWebView2.ExecuteScriptAsync("""
                (() => {
                  const root = document.getElementById('root');
                  const rect = root ? root.getBoundingClientRect() : null;
                  const styles = root ? getComputedStyle(root) : null;
                  return JSON.stringify({
                    url: location.href,
                    title: document.title,
                    readyState: document.readyState,
                    viewport: `${window.innerWidth}x${window.innerHeight}`,
                    rootChildren: root ? root.childElementCount : -1,
                    rootRect: rect ? `${Math.round(rect.left)},${Math.round(rect.top)},${Math.round(rect.width)}x${Math.round(rect.height)}` : '',
                    rootStyle: styles ? `${styles.display};${styles.visibility};${styles.opacity}` : ''
                  });
                })();
                """).AsTask();
            ShellLogger.Info($"WebView2 page state ({phase}): {result}");
            if (capturePreview)
            {
                await CaptureWebViewPreviewAsync(browser, phase);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to read WebView2 page state.");
        }
    }

    private static async Task CaptureWebViewPreviewAsync(WebView2 browser, string phase)
    {
        try
        {
            if (browser.CoreWebView2 == null)
            {
                return;
            }

            AppPaths.EnsureLogsDirectory();
            var folder = await StorageFolder.GetFolderFromPathAsync(AppPaths.LogsDirectory);
            var file = await folder.CreateFileAsync($"webview-preview-{phase}.png", CreationCollisionOption.ReplaceExisting);
            using var stream = await file.OpenAsync(FileAccessMode.ReadWrite);
            await browser.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream).AsTask();
            ShellLogger.Info($"WebView2 preview captured ({phase}): {file.Path}; bytes={stream.Size}");
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to capture WebView2 preview ({phase}).");
        }
    }

    private void ShowStartupFailure(Exception ex)
    {
        _loadingOverlay.Visibility = Visibility.Visible;
        _statusText.Text = $"启动失败：{ex.Message}";
        _actionsPanel.Children.Clear();
        _actionsPanel.Visibility = Visibility.Visible;

        var browserButton = new Button
        {
            Content = "在浏览器打开",
        };
        browserButton.Click += (_, _) =>
        {
            if (_backendUri == null)
            {
                return;
            }

            Process.Start(new ProcessStartInfo
            {
                FileName = _backendUri.ToString(),
                UseShellExecute = true,
            });
        };

        var logsButton = new Button
        {
            Content = "打开日志",
        };
        logsButton.Click += (_, _) => OpenLogsDirectory();

        _actionsPanel.Children.Add(browserButton);
        _actionsPanel.Children.Add(logsButton);
    }

    private async void OnWebMessageReceived(CoreWebView2 sender, CoreWebView2WebMessageReceivedEventArgs args)
    {
        try
        {
            using var document = JsonDocument.Parse(args.WebMessageAsJson);
            var root = document.RootElement;
            var id = root.TryGetProperty("id", out var idProperty) ? idProperty.GetString() ?? "" : "";
            var action = root.TryGetProperty("action", out var actionProperty) ? actionProperty.GetString() ?? "" : "";

            switch (action)
            {
                case "getShellInfo":
                    PostWebMessageResult(id, new { version = "1", runtime = "windows", backendUrl = _backendUri?.ToString() });
                    break;
                case "pickFolder":
                    PostWebMessageResult(id, await PickFolderAsync());
                    break;
                case "openLogs":
                    OpenLogsDirectory();
                    PostWebMessageResult(id, true);
                    break;
                case "restartBackend":
                    await _backend.RestartAsync();
                    PostWebMessageResult(id, true);
                    break;
                case "openMpv":
                    var url = root.TryGetProperty("url", out var urlProperty) ? urlProperty.GetString() ?? "" : "";
                    OpenMpv(url);
                    PostWebMessageResult(id, true);
                    break;
                case "logClientError":
                    LogClientError(root);
                    break;
                default:
                    PostWebMessageError(id, $"Unknown action: {action}");
                    break;
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to handle WebView2 message.");
            PostWebMessageError("", ex.Message);
        }
    }

    private static void LogClientError(JsonElement root)
    {
        var message = root.TryGetProperty("message", out var messageProperty) ? messageProperty.GetString() ?? "" : "";
        var source = root.TryGetProperty("source", out var sourceProperty) ? sourceProperty.GetString() ?? "" : "";
        var line = root.TryGetProperty("line", out var lineProperty) ? lineProperty.GetInt32() : 0;
        var column = root.TryGetProperty("column", out var columnProperty) ? columnProperty.GetInt32() : 0;
        ShellLogger.Error($"WebView2 client error: {message} ({source}:{line}:{column})");
    }

    private async Task<string> PickFolderAsync()
    {
        var picker = new FolderPicker
        {
            SuggestedStartLocation = PickerLocationId.VideosLibrary,
        };
        picker.FileTypeFilter.Add("*");
        InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
        var folder = await picker.PickSingleFolderAsync();
        return folder?.Path ?? "";
    }

    private static void OpenMpv(string url)
    {
        if (string.IsNullOrWhiteSpace(url))
        {
            throw new InvalidOperationException("MPV playback URL is empty.");
        }

        var player = new MpvPlayerWindow(url);
        player.Activate();
    }

    private static void OpenLogsDirectory()
    {
        AppPaths.EnsureLogsDirectory();
        Process.Start(new ProcessStartInfo
        {
            FileName = AppPaths.LogsDirectory,
            UseShellExecute = true,
        });
    }

    private void PostWebMessageResult(string id, object result)
    {
        _browser?.CoreWebView2?.PostWebMessageAsJson(JsonSerializer.Serialize(new
        {
            id,
            ok = true,
            result,
        }));
    }

    private void PostWebMessageError(string id, string message)
    {
        _browser?.CoreWebView2?.PostWebMessageAsJson(JsonSerializer.Serialize(new
        {
            id,
            ok = false,
            error = message,
        }));
    }

    private void OnClosed(object sender, WindowEventArgs args)
    {
        _backend.Dispose();
    }
}
