using System;
using Microsoft.UI.Xaml;
using MediaTree.Windows.Services;

namespace MediaTree.Windows;

public partial class App : Application
{
    private MainWindow? _window;

    public App()
    {
        UnhandledException += OnUnhandledException;
        RequestedTheme = ApplicationTheme.Light;
        InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        try
        {
            ShellLogger.Info("Launching MediaTree Windows shell.");
            _window = new MainWindow();
            _window.ShowAndBringToFront();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Launch failed.");
            throw;
        }
    }

    private void OnUnhandledException(object sender, Microsoft.UI.Xaml.UnhandledExceptionEventArgs args)
    {
        ShellLogger.Error(args.Exception, "Unhandled WinUI exception.");
        args.Handled = true;
    }
}
