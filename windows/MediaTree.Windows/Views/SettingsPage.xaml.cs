using System;
using System.Diagnostics;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace MediaTree.Windows.Views;

public sealed partial class SettingsPage : Page
{
    private readonly TextBlock _updateStatusText;
    private readonly TextBlock _versionText;

    public SettingsPage()
    {
        (_versionText, _updateStatusText) = BuildContent();
        Loaded += async (_, _) => await LoadVersionAsync();
    }

    private (TextBlock versionText, TextBlock updateStatusText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "SettingsPage");

        var scrollViewer = new ScrollViewer();
        var root = new StackPanel
        {
            Padding = new Thickness(40),
            Spacing = 22,
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.Children.Add(FluentTheme.Title("设置", 34));

        var card = new Border
        {
            Padding = new Thickness(22),
            CornerRadius = new CornerRadius(16),
            Background = FluentTheme.Layer,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
        };
        var stack = new StackPanel { Spacing = 12 };
        stack.Children.Add(new TextBlock
        {
            Text = "版本与更新",
            FontSize = 20,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
        });

        var versionText = new TextBlock
        {
            Foreground = FluentTheme.TextSecondary,
        };
        AutomationProperties.SetAutomationId(versionText, "SettingsVersion");
        stack.Children.Add(versionText);

        var updateStatusText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(updateStatusText, "SettingsUpdateStatusText");
        stack.Children.Add(updateStatusText);

        var actions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 10,
        };
        var checkButton = FluentTheme.ApplyButton(new Button
        {
            Content = "检查更新",
        });
        AutomationProperties.SetAutomationId(checkButton, "SettingsCheckUpdates");
        checkButton.Click += OnCheckUpdatesClicked;
        actions.Children.Add(checkButton);

        var logsButton = FluentTheme.ApplyButton(new Button
        {
            Content = "打开问题日志",
        });
        AutomationProperties.SetAutomationId(logsButton, "SettingsOpenLogs");
        logsButton.Click += OnOpenLogsClicked;
        actions.Children.Add(logsButton);

        var addLibraryButton = FluentTheme.ApplyButton(new Button
        {
            Content = "添加影片文件夹",
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(addLibraryButton, "SettingsAddLibrary");
        addLibraryButton.Click += OnAddLibraryClicked;
        actions.Children.Add(addLibraryButton);

        stack.Children.Add(actions);
        card.Child = stack;
        root.Children.Add(card);
        scrollViewer.Content = root;
        Content = scrollViewer;
        return (versionText, updateStatusText);
    }

    private async System.Threading.Tasks.Task LoadVersionAsync()
    {
        try
        {
            var version = await AppServices.Updates.GetVersionAsync();
            var source = version.CurrentSource == "app-package" ? "已更新的应用包" : "安装包内置版本";
            _versionText.Text = $"当前版本：{version.Version}    来源：{source}";
        }
        catch (Exception ex)
        {
            _versionText.Text = $"暂时无法读取版本信息：{ex.Message}";
        }
    }

    private async void OnCheckUpdatesClicked(object sender, RoutedEventArgs args)
    {
        try
        {
            var result = await AppServices.Updates.CheckForUpdatesAsync();
            if (!result.HasUpdate)
            {
                ShowUpdateStatus("当前已经是最新版本。", false);
            }
            else
            {
                var next = result.Versions.Count > 0 ? result.Versions[0] : null;
                var message = next?.RequiresWindowsBaseUpdate == true
                    ? $"发现新版本 {next.DisplayVersion}。这次更新需要安装新的 Windows 桌面版安装包。{next.WindowsReason}"
                    : $"发现新版本 {next?.DisplayVersion}。可以直接在应用内更新。";
                ShowUpdateStatus(message, false);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to check native Windows updates.");
            ShowUpdateStatus($"检查更新失败：{ex.Message}", true);
        }
    }

    private void OnOpenLogsClicked(object sender, RoutedEventArgs args)
    {
        try
        {
            AppPaths.EnsureLogsDirectory();
            Process.Start(new ProcessStartInfo
            {
                FileName = AppPaths.LogsDirectory,
                UseShellExecute = true,
            });
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to open native Windows logs directory.");
            ShowUpdateStatus($"打开日志失败：{ex.Message}", true);
        }
    }

    private void OnAddLibraryClicked(object sender, RoutedEventArgs args)
    {
        ShellPage.Current?.NavigateToSetup();
    }

    private void ShowUpdateStatus(string message, bool isError)
    {
        _updateStatusText.Text = message;
        _updateStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _updateStatusText.Visibility = Visibility.Visible;
    }

}
