using System;
using System.Threading.Tasks;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;

namespace MediaTree.Windows.Platform;

public sealed class WindowModalDialog
{
    private readonly UIElement _content;
    private readonly string _title;
    private readonly string _primaryText;
    private readonly string _closeText;
    private Grid? _overlay;
    private TaskCompletionSource<bool>? _completion;

    public WindowModalDialog(string title, UIElement content, string primaryText, string closeText = "取消")
    {
        _title = title;
        _content = content;
        _primaryText = primaryText;
        _closeText = closeText;
    }

    public double MaxWidth { get; init; } = 760;
    public double ContentMaxWidth { get; init; } = 720;
    public double ContentMaxHeight { get; init; } = 560;
    public Func<Task<bool>>? PrimaryActionAsync { get; set; }
    public bool IsPrimaryButtonEnabled { get; set; } = true;

    public async Task ShowAsync()
    {
        if (AppServices.MainWindow?.Content is not Panel windowRoot)
        {
            throw new InvalidOperationException("Main window root panel is not available.");
        }

        _completion = new TaskCompletionSource<bool>();
        _overlay = BuildOverlay();
        windowRoot.Children.Add(_overlay);

        await _completion.Task;
        windowRoot.Children.Remove(_overlay);
        _overlay = null;
        _completion = null;
    }

    public void Hide()
    {
        _completion?.TrySetResult(true);
    }

    private Grid BuildOverlay()
    {
        var overlay = new Grid
        {
            Background = FluentTheme.Brush(0x00, 0x00, 0x00, 0x5C),
            HorizontalAlignment = HorizontalAlignment.Stretch,
            VerticalAlignment = VerticalAlignment.Stretch,
            IsHitTestVisible = true,
        };
        overlay.KeyDown += OnOverlayKeyDown;

        var titleBlock = new TextBlock
        {
            Text = _title,
            FontSize = 22,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };

        var body = new ScrollViewer
        {
            Content = _content,
            MaxWidth = ContentMaxWidth,
            MaxHeight = ContentMaxHeight,
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
        };

        var primaryButton = FluentTheme.ApplyButton(new Button
        {
            Content = _primaryText,
            MinWidth = 170,
            IsEnabled = IsPrimaryButtonEnabled,
        }, FluentButtonStyle.Accent);
        primaryButton.Click += async (_, _) =>
        {
            if (PrimaryActionAsync is null)
            {
                Hide();
                return;
            }

            primaryButton.IsEnabled = false;
            var shouldClose = false;
            try
            {
                shouldClose = await PrimaryActionAsync();
            }
            finally
            {
                if (!shouldClose)
                {
                    primaryButton.IsEnabled = IsPrimaryButtonEnabled;
                }
            }

            if (shouldClose)
            {
                Hide();
            }
        };

        var closeButton = FluentTheme.ApplyButton(new Button
        {
            Content = _closeText,
            MinWidth = 170,
        });
        closeButton.Click += (_, _) => Hide();

        var footer = new Grid
        {
            ColumnSpacing = 12,
            Padding = new Thickness(20, 16, 20, 20),
            Background = FluentTheme.LayerAlt,
        };
        footer.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        footer.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        footer.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        Grid.SetColumn(primaryButton, 1);
        Grid.SetColumn(closeButton, 2);
        footer.Children.Add(primaryButton);
        footer.Children.Add(closeButton);

        var contentStack = new StackPanel
        {
            Spacing = 16,
            Padding = new Thickness(24, 24, 24, 20),
        };
        contentStack.Children.Add(titleBlock);
        contentStack.Children.Add(body);

        var cardStack = new Grid();
        cardStack.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        cardStack.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        cardStack.Children.Add(contentStack);
        Grid.SetRow(footer, 1);
        cardStack.Children.Add(footer);

        var card = new Border
        {
            MaxWidth = MaxWidth,
            CornerRadius = FluentTheme.CardCornerRadius,
            Background = FluentTheme.Layer,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Child = cardStack,
        };

        overlay.Children.Add(card);
        return overlay;
    }

    private void OnOverlayKeyDown(object sender, KeyRoutedEventArgs args)
    {
        if (args.Key == global::Windows.System.VirtualKey.Escape)
        {
            args.Handled = true;
            Hide();
        }
    }
}
