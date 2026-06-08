using System;
using System.Runtime.InteropServices;
using MediaTree.Windows.Services;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using WinRT;

namespace MediaTree.Windows.Controls;

public sealed partial class MpvPlayerControl : UserControl
{
    private readonly SwapChainPanel _playerSwapChainPanel;
    private readonly TextBlock _statusText;
    private IMpvPlayerService? _player;
    private IntPtr _currentSwapChain;
    private IntPtr _pendingSwapChain;
    private bool _isLoaded;

    public MpvPlayerControl()
    {
        (_playerSwapChainPanel, _statusText) = BuildContent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        SizeChanged += (_, _) =>
        {
            UpdateCompositionSize();
            BindPendingSwapChain();
        };
    }

    private (SwapChainPanel playerSwapChainPanel, TextBlock statusText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "MpvPlayerControl");

        var root = new Grid
        {
            Background = new SolidColorBrush(Microsoft.UI.Colors.Black),
        };

        var playerSwapChainPanel = new SwapChainPanel();
        AutomationProperties.SetAutomationId(playerSwapChainPanel, "MpvSwapChainPanel");
        root.Children.Add(playerSwapChainPanel);

        var statusText = new TextBlock
        {
            Text = "正在初始化 libmpv...",
            Foreground = new SolidColorBrush(Microsoft.UI.Colors.White),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };
        root.Children.Add(statusText);

        Content = root;
        return (playerSwapChainPanel, statusText);
    }

    public void AttachService(IMpvPlayerService player)
    {
        if (_player != null)
        {
            _player.DisplaySwapchainChanged -= OnDisplaySwapchainChanged;
        }

        _player = player;
        _player.DisplaySwapchainChanged += OnDisplaySwapchainChanged;
        UpdateCompositionSize();
        _ = DispatcherQueue.TryEnqueue(UpdateCompositionSize);
    }

    private void OnDisplaySwapchainChanged(object? sender, IntPtr swapChain)
    {
        if (!DispatcherQueue.TryEnqueue(() => QueueSwapChainBind(swapChain)))
        {
            ShellLogger.Error("Failed to queue libmpv swapchain binding.");
        }
    }

    private void QueueSwapChainBind(IntPtr swapChain)
    {
        if (swapChain == IntPtr.Zero)
        {
            return;
        }

        _pendingSwapChain = swapChain;
        BindPendingSwapChain();
    }

    private void BindPendingSwapChain()
    {
        if (!_isLoaded || _pendingSwapChain == IntPtr.Zero || _pendingSwapChain == _currentSwapChain)
        {
            return;
        }

        UpdateCompositionSize();
        if (!HasCompositionSize())
        {
            return;
        }

        try
        {
            var native = _playerSwapChainPanel.As<ISwapChainPanelNative>();
            native.SetSwapChain(_pendingSwapChain);
            _currentSwapChain = _pendingSwapChain;
            _statusText.Visibility = Visibility.Collapsed;
            ShellLogger.Info($"Bound libmpv display swapchain 0x{_currentSwapChain.ToInt64():X}.");
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to bind libmpv display swapchain.");
        }
    }

    private void UpdateCompositionSize()
    {
        if (_player is not LibMpvPlayerService libMpv)
        {
            return;
        }

        var width = _playerSwapChainPanel.ActualWidth > 0 ? _playerSwapChainPanel.ActualWidth : ActualWidth;
        var height = _playerSwapChainPanel.ActualHeight > 0 ? _playerSwapChainPanel.ActualHeight : ActualHeight;
        libMpv.UpdateCompositionSize(width, height);
    }

    private bool HasCompositionSize()
    {
        var width = _playerSwapChainPanel.ActualWidth > 0 ? _playerSwapChainPanel.ActualWidth : ActualWidth;
        var height = _playerSwapChainPanel.ActualHeight > 0 ? _playerSwapChainPanel.ActualHeight : ActualHeight;
        return width > 0 && height > 0;
    }

    private void OnLoaded(object sender, RoutedEventArgs args)
    {
        _isLoaded = true;
        UpdateCompositionSize();
        BindPendingSwapChain();
    }

    private void OnUnloaded(object sender, RoutedEventArgs args)
    {
        _isLoaded = false;
        if (_player != null)
        {
            _player.DisplaySwapchainChanged -= OnDisplaySwapchainChanged;
        }

        try
        {
            var native = _playerSwapChainPanel.As<ISwapChainPanelNative>();
            native.SetSwapChain(IntPtr.Zero);
            _currentSwapChain = IntPtr.Zero;
            _pendingSwapChain = IntPtr.Zero;
        }
        catch
        {
            // WinUI may already be tearing down the native panel.
        }
    }

    [ComImport]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    [Guid("63AAD0B8-7C24-40FF-85A8-640D944CC325")]
    private interface ISwapChainPanelNative
    {
        void SetSwapChain(IntPtr swapChain);
    }
}
