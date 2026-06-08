using System;
using System.Runtime.InteropServices;
using MediaTree.Windows.Services;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace MediaTree.Windows.Controls;

public sealed partial class MpvPlayerControl : UserControl
{
    private readonly SwapChainPanel _playerSwapChainPanel;
    private readonly TextBlock _statusText;
    private IMpvPlayerService? _player;
    private IntPtr _currentSwapChain;

    public MpvPlayerControl()
    {
        (_playerSwapChainPanel, _statusText) = BuildContent();
        Unloaded += OnUnloaded;
        SizeChanged += (_, _) =>
        {
            if (_player is LibMpvPlayerService libMpv)
            {
                libMpv.UpdateCompositionSize(ActualWidth, ActualHeight);
            }

            BindSwapChain(_currentSwapChain);
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
    }

    private void OnDisplaySwapchainChanged(object? sender, IntPtr swapChain)
    {
        DispatcherQueue.TryEnqueue(() => BindSwapChain(swapChain));
    }

    private void BindSwapChain(IntPtr swapChain)
    {
        _currentSwapChain = swapChain;
        if (swapChain == IntPtr.Zero)
        {
            return;
        }

        var native = (ISwapChainPanelNative)(object)_playerSwapChainPanel;
        native.SetSwapChain(swapChain);
        _statusText.Visibility = Visibility.Collapsed;
    }

    private void OnUnloaded(object sender, RoutedEventArgs args)
    {
        if (_player != null)
        {
            _player.DisplaySwapchainChanged -= OnDisplaySwapchainChanged;
        }

        try
        {
            var native = (ISwapChainPanelNative)(object)_playerSwapChainPanel;
            native.SetSwapChain(IntPtr.Zero);
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
