using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace MediaTree.Windows.Styles;

public static class FluentTheme
{
    public static SolidColorBrush Canvas => Brush(0xF3, 0xF3, 0xF3);
    public static SolidColorBrush Layer => Brush(0xFF, 0xFF, 0xFF);
    public static SolidColorBrush LayerAlt => Brush(0xF9, 0xFA, 0xFB);
    public static SolidColorBrush Border => Brush(0, 0, 0, 0x14);
    public static SolidColorBrush TextPrimary => Brush(0x1A, 0x1A, 0x1A);
    public static SolidColorBrush TextSecondary => Brush(0x5F, 0x66, 0x73);
    public static SolidColorBrush TextTertiary => Brush(0x7A, 0x84, 0x92);
    public static SolidColorBrush Accent => Brush(0x00, 0x5F, 0xB8);
    public static SolidColorBrush AccentSoft => Brush(0xE5, 0xF1, 0xFB);
    public static SolidColorBrush AccentText => Brush(0xFF, 0xFF, 0xFF);
    public static SolidColorBrush Control => Brush(0xFB, 0xFB, 0xFB);
    public static SolidColorBrush ControlAlt => Brush(0xF1, 0xF3, 0xF5);
    public static SolidColorBrush OverlayControl => Brush(0x2B, 0x2F, 0x36, 0xE8);
    public static SolidColorBrush Success => Brush(0x0F, 0x7B, 0x0F);
    public static SolidColorBrush Error => Brush(0xB3, 0x26, 0x1E);
    public static CornerRadius ControlCornerRadius => new(6);

    public static SolidColorBrush Brush(byte r, byte g, byte b, byte a = 0xFF)
    {
        return new SolidColorBrush(Microsoft.UI.ColorHelper.FromArgb(a, r, g, b));
    }

    public static TextBlock Title(string text, double fontSize = 28)
    {
        return new TextBlock
        {
            Text = text,
            FontSize = fontSize,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
    }

    public static TextBlock Body(string text, double fontSize = 14)
    {
        return new TextBlock
        {
            Text = text,
            FontSize = fontSize,
            Foreground = TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
    }

    public static Border Card(UIElement child, Thickness? padding = null)
    {
        return new Border
        {
            Padding = padding ?? new Thickness(20),
            CornerRadius = new CornerRadius(12),
            Background = Layer,
            BorderBrush = Border,
            BorderThickness = new Thickness(1),
            Child = child,
        };
    }

    public static Border CenteredCard(UIElement child, double maxWidth = 560, Thickness? padding = null)
    {
        return new Border
        {
            Padding = padding ?? new Thickness(24),
            CornerRadius = new CornerRadius(12),
            Background = Layer,
            BorderBrush = Border,
            BorderThickness = new Thickness(1),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            MaxWidth = maxWidth,
            Margin = new Thickness(24),
            Child = child,
        };
    }

    public static Button ApplyButton(Button button, FluentButtonStyle style = FluentButtonStyle.Standard)
    {
        button.CornerRadius = ControlCornerRadius;
        button.Padding = new Thickness(14, 8, 14, 8);
        button.MinHeight = button.MinHeight > 0 ? button.MinHeight : 36;

        switch (style)
        {
            case FluentButtonStyle.Accent:
                button.Background = Accent;
                button.Foreground = AccentText;
                button.BorderBrush = Accent;
                break;
            case FluentButtonStyle.Subtle:
                button.Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
                button.Foreground = TextPrimary;
                button.BorderBrush = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
                break;
            case FluentButtonStyle.Overlay:
                button.Background = OverlayControl;
                button.Foreground = AccentText;
                button.BorderBrush = Brush(0xFF, 0xFF, 0xFF, 0x24);
                break;
            default:
                button.Background = Control;
                button.Foreground = TextPrimary;
                button.BorderBrush = Border;
                break;
        }

        return button;
    }
}

public enum FluentButtonStyle
{
    Standard,
    Accent,
    Subtle,
    Overlay,
}
