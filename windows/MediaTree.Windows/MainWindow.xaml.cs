using System;
using System.Diagnostics;
using System.Threading.Tasks;
using MediaTree.Windows.Models;
using MediaTree.Windows.Providers;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using MediaTree.Windows.Views;
using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using WinRT.Interop;

namespace MediaTree.Windows;

public sealed partial class MainWindow : Window
{
    private const string DefaultWindowTitle = "MediaTree";
    private readonly BackendProcessService _backend = new();
    private readonly Frame _rootFrame;
    private readonly Grid _loadingOverlay;
    private readonly TextBlock _statusText;
    private readonly StackPanel _startupActions;
    private AppWindow? _appWindow;
    private bool _isFullScreen;
    private bool _startupStarted;

    public MainWindow()
    {
        ShellLogger.Info("Creating native main window.");
        Title = DefaultWindowTitle;
        Closed += OnClosed;
        (_rootFrame, _loadingOverlay, _statusText, _startupActions) = BuildContent();
    }

    public void ShowAndBringToFront()
    {
        Activate();

        var hwnd = WindowNative.GetWindowHandle(this);
        ShellLogger.Info($"Main window activated. HWND=0x{hwnd.ToInt64():X}.");
        BeginStartup();
    }

    public void NavigateToShell()
    {
        ShellLogger.Info("Navigating to native shell page.");
        _loadingOverlay.Visibility = Visibility.Collapsed;
        _rootFrame.Navigate(typeof(ShellPage));
        ShellLogger.Info("Native shell page navigation requested.");
    }

    public void NavigateToLogin()
    {
        ShellLogger.Info("Navigating to native login page.");
        _loadingOverlay.Visibility = Visibility.Collapsed;
        _rootFrame.Navigate(typeof(LoginPage));
        ShellLogger.Info("Native login page navigation requested.");
    }

    public void SetFullScreen(bool enabled)
    {
        var appWindow = GetAppWindow();
        if (enabled == _isFullScreen)
        {
            return;
        }

        appWindow.SetPresenter(enabled ? AppWindowPresenterKind.FullScreen : AppWindowPresenterKind.Overlapped);
        _isFullScreen = enabled;
    }

    public void SetPlaybackWindowTitle(string? title, bool paused)
    {
        if (string.IsNullOrWhiteSpace(title))
        {
            RestoreDefaultWindowTitle();
            return;
        }

        var playbackTitle = title.Trim();
        Title = $"{(paused ? "⏸" : "▶")} {playbackTitle} - {DefaultWindowTitle}";
    }

    public void RestoreDefaultWindowTitle()
    {
        Title = DefaultWindowTitle;
    }

    private AppWindow GetAppWindow()
    {
        if (_appWindow is not null)
        {
            return _appWindow;
        }

        var hwnd = WindowNative.GetWindowHandle(this);
        var windowId = Win32Interop.GetWindowIdFromWindow(hwnd);
        _appWindow = AppWindow.GetFromWindowId(windowId);
        return _appWindow;
    }

    private (Frame rootFrame, Grid loadingOverlay, TextBlock statusText, StackPanel startupActions) BuildContent()
    {
        var root = new Grid
        {
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };

        var rootFrame = new Frame();
        AutomationProperties.SetAutomationId(rootFrame, "RootFrame");
        root.Children.Add(rootFrame);

        var loadingOverlay = new Grid
        {
            Background = FluentTheme.Canvas,
            Visibility = Visibility.Visible,
        };
        AutomationProperties.SetAutomationId(loadingOverlay, "StartupOverlay");

        var stack = new StackPanel
        {
            HorizontalAlignment = HorizontalAlignment.Stretch,
            MaxWidth = 480,
            Spacing = 14,
        };

        var startupTitle = FluentTheme.Title("正在打开 MediaTree", 24);
        startupTitle.HorizontalAlignment = HorizontalAlignment.Stretch;
        startupTitle.TextAlignment = TextAlignment.Center;
        AutomationProperties.SetAutomationId(startupTitle, "StartupTitle");
        stack.Children.Add(startupTitle);
        stack.Children.Add(new TextBlock
        {
            Text = "请稍候，MediaTree 正在准备本机媒体库和播放器。",
            Foreground = FluentTheme.TextSecondary,
            TextAlignment = TextAlignment.Center,
            TextWrapping = TextWrapping.WrapWholeWords,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        });

        var statusText = new TextBlock
        {
            Text = "正在准备本机媒体服务，请稍候...",
            Foreground = FluentTheme.TextTertiary,
            TextAlignment = TextAlignment.Center,
            TextWrapping = TextWrapping.WrapWholeWords,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        AutomationProperties.SetAutomationId(statusText, "StartupStatusText");
        stack.Children.Add(statusText);

        var startupActions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Center,
            Spacing = 10,
            Visibility = Visibility.Collapsed,
        };
        stack.Children.Add(startupActions);

        loadingOverlay.Children.Add(FluentTheme.CenteredCard(stack, maxWidth: 540, padding: new Thickness(30)));
        root.Children.Add(loadingOverlay);
        Content = root;

        return (rootFrame, loadingOverlay, statusText, startupActions);
    }

    private void BeginStartup()
    {
        if (_startupStarted)
        {
            return;
        }

        _startupStarted = true;
        ShellLogger.Info("Queueing native startup pipeline.");
        _ = StartAsync();
    }

    private async Task StartAsync()
    {
        try
        {
            ShellLogger.Info("Native startup pipeline started.");
            AppServices.MainWindow = this;
            _statusText.Text = "正在启动本机媒体服务";
            var backendUri = await _backend.StartAsync();

            _statusText.Text = "正在准备登录状态";
            var api = new MediaTreeApiClient(backendUri);
            var mediaTreeServices = new MediaTreeServices(
                api,
                new AuthSessionService(api),
                new LibraryService(api),
                new MovieService(api),
                new UpdateService(api),
                new PlaybackProgressService(api));
            var provider = new LocalMediaTreeProvider(mediaTreeServices);
            AppServices.Initialize(
                backend: _backend,
                provider: provider);

            var session = await AppServices.MediaTree.Auth.EnsureLocalSessionAsync();
            ShellLogger.Info($"Native session result: {session.State}.");
            if (session.State == AuthSessionState.NeedsUserLogin)
            {
                NavigateToLogin();
                return;
            }

            NavigateToShell();
        }
        catch (Exception ex)
        {
            Debug.WriteLine(ex);
            ShellLogger.Error(ex, "Native main window startup failed.");
            ShowStartupFailure(ex);
        }
    }

    private void ShowStartupFailure(Exception ex)
    {
        _loadingOverlay.Visibility = Visibility.Visible;
        _statusText.Text = $"MediaTree 没能启动：{ex.Message}";
        _startupActions.Children.Clear();
        _startupActions.Visibility = Visibility.Visible;

        var restartButton = FluentTheme.ApplyButton(new Button
        {
            Content = "再试一次",
            MinWidth = 92,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(restartButton, "StartupRetryButton");
        restartButton.Click += (_, _) =>
        {
            _startupActions.Visibility = Visibility.Collapsed;
            _statusText.Text = "正在重新打开 MediaTree";
            _ = StartAsync();
        };

        var logsButton = FluentTheme.ApplyButton(new Button
        {
            Content = "查看日志",
            MinWidth = 92,
        });
        AutomationProperties.SetAutomationId(logsButton, "StartupOpenLogs");
        logsButton.Click += (_, _) => OpenLogsDirectory();

        _startupActions.Children.Add(restartButton);
        _startupActions.Children.Add(logsButton);
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

    private void OnClosed(object sender, WindowEventArgs args)
    {
        AppServices.Dispose();
        _backend.Dispose();
    }
}
