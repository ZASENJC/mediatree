using System.Numerics;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Hosting;
using Microsoft.UI.Xaml.Media;

namespace MediaTree.Windows.Styles;

public static class FluentTheme
{
    public const double CompactBreakpoint = 760;
    public const double MediumBreakpoint = 980;
    private const string ButtonInteractionStateResourceKey = "MediaTreeButtonInteractionState";

    public static SolidColorBrush Canvas => Brush(0xF3, 0xF3, 0xF3);
    public static SolidColorBrush Layer => Brush(0xFF, 0xFF, 0xFF);
    public static SolidColorBrush LayerAlt => Brush(0xF9, 0xFA, 0xFB);
    public static SolidColorBrush Border => Brush(0, 0, 0, 0x14);
    public static SolidColorBrush TextPrimary => Brush(0x1A, 0x1A, 0x1A);
    public static SolidColorBrush TextSecondary => Brush(0x5F, 0x66, 0x73);
    public static SolidColorBrush TextTertiary => Brush(0x7A, 0x84, 0x92);
    public static SolidColorBrush Accent => Brush(0x00, 0x5F, 0xB8);
    public static SolidColorBrush AccentHover => Brush(0x00, 0x6E, 0xD6);
    public static SolidColorBrush AccentPressed => Brush(0x00, 0x4F, 0x99);
    public static SolidColorBrush AccentSoft => Brush(0xE5, 0xF1, 0xFB);
    public static SolidColorBrush AccentText => Brush(0xFF, 0xFF, 0xFF);
    public static SolidColorBrush Control => Brush(0xFB, 0xFB, 0xFB);
    public static SolidColorBrush ControlAlt => Brush(0xF1, 0xF3, 0xF5);
    public static SolidColorBrush ControlHover => Brush(0xF4, 0xF7, 0xFA);
    public static SolidColorBrush ControlPressed => Brush(0xE9, 0xED, 0xF3);
    public static SolidColorBrush OverlayControl => Brush(0x2B, 0x2F, 0x36, 0xE8);
    public static SolidColorBrush OverlayControlHover => Brush(0x36, 0x3C, 0x45, 0xF2);
    public static SolidColorBrush OverlayControlPressed => Brush(0x20, 0x24, 0x2B, 0xF2);
    public static SolidColorBrush Success => Brush(0x0F, 0x7B, 0x0F);
    public static SolidColorBrush Error => Brush(0xB3, 0x26, 0x1E);
    public static SolidColorBrush ErrorHover => Brush(0xC4, 0x2F, 0x27);
    public static SolidColorBrush ErrorPressed => Brush(0x93, 0x1F, 0x19);
    public static CornerRadius ControlCornerRadius => new(8);
    public static CornerRadius CardCornerRadius => new(8);
    public static CornerRadius MediaCornerRadius => new(8);

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
            CornerRadius = CardCornerRadius,
            Background = Layer,
            BorderBrush = Border,
            BorderThickness = new Thickness(1),
            HorizontalAlignment = HorizontalAlignment.Stretch,
            Child = child,
        };
    }

    public static Border CenteredCard(UIElement child, double maxWidth = 560, Thickness? padding = null)
    {
        return new Border
        {
            Padding = padding ?? new Thickness(24),
            CornerRadius = CardCornerRadius,
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
        button.UseSystemFocusVisuals = true;
        button.Translation = Vector3.Zero;

        switch (style)
        {
            case FluentButtonStyle.Accent:
                button.Background = Accent;
                button.Foreground = AccentText;
                button.BorderBrush = Accent;
                ApplyButtonStateResources(
                    button,
                    AccentHover,
                    AccentPressed,
                    AccentHover,
                    AccentPressed,
                    AccentText,
                    AccentText);
                AttachButtonElevation(button, elevated: true);
                break;
            case FluentButtonStyle.Subtle:
                button.Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
                button.Foreground = TextPrimary;
                button.BorderBrush = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
                ApplyButtonStateResources(
                    button,
                    ControlAlt,
                    ControlPressed,
                    new SolidColorBrush(Microsoft.UI.Colors.Transparent),
                    new SolidColorBrush(Microsoft.UI.Colors.Transparent),
                    TextPrimary,
                    TextPrimary);
                AttachButtonElevation(button, elevated: false);
                break;
            case FluentButtonStyle.Overlay:
                button.Background = OverlayControl;
                button.Foreground = AccentText;
                button.BorderBrush = Brush(0xFF, 0xFF, 0xFF, 0x24);
                ApplyButtonStateResources(
                    button,
                    OverlayControlHover,
                    OverlayControlPressed,
                    Brush(0xFF, 0xFF, 0xFF, 0x38),
                    Brush(0xFF, 0xFF, 0xFF, 0x20),
                    AccentText,
                    AccentText);
                AttachButtonElevation(button, elevated: false);
                break;
            case FluentButtonStyle.Danger:
                button.Background = Error;
                button.Foreground = AccentText;
                button.BorderBrush = Error;
                ApplyButtonStateResources(
                    button,
                    ErrorHover,
                    ErrorPressed,
                    ErrorHover,
                    ErrorPressed,
                    AccentText,
                    AccentText);
                AttachButtonElevation(button, elevated: true);
                break;
            default:
                button.Background = Control;
                button.Foreground = TextPrimary;
                button.BorderBrush = Border;
                ApplyButtonStateResources(
                    button,
                    ControlHover,
                    ControlPressed,
                    Brush(0x00, 0x5F, 0xB8, 0x3D),
                    Brush(0x00, 0x5F, 0xB8, 0x33),
                    TextPrimary,
                    TextPrimary);
                AttachButtonElevation(button, elevated: false);
                break;
        }

        return button;
    }

    private static void ApplyButtonStateResources(
        Button button,
        Brush pointerOverBackground,
        Brush pressedBackground,
        Brush pointerOverBorder,
        Brush pressedBorder,
        Brush pointerOverForeground,
        Brush pressedForeground)
    {
        button.Resources["ButtonBackgroundPointerOver"] = pointerOverBackground;
        button.Resources["ButtonBackgroundPressed"] = pressedBackground;
        button.Resources["ButtonBorderBrushPointerOver"] = pointerOverBorder;
        button.Resources["ButtonBorderBrushPressed"] = pressedBorder;
        button.Resources["ButtonForegroundPointerOver"] = pointerOverForeground;
        button.Resources["ButtonForegroundPressed"] = pressedForeground;
    }

    private static void AttachButtonElevation(Button button, bool elevated)
    {
        if (button.Resources.ContainsKey(ButtonInteractionStateResourceKey)
            && button.Resources[ButtonInteractionStateResourceKey] is ButtonInteractionState existingState)
        {
            existingState.Elevated = elevated;
            return;
        }

        var state = new ButtonInteractionState { Elevated = elevated };
        button.Resources[ButtonInteractionStateResourceKey] = state;
        ElementCompositionPreview.SetIsTranslationEnabled(button, true);
        button.PointerEntered += (_, _) =>
        {
            if (!button.IsEnabled)
            {
                return;
            }

            button.Shadow = new ThemeShadow();
            button.Translation = new Vector3(0, 0, state.Elevated ? 12 : 4);
        };
        button.PointerExited += (_, _) =>
        {
            button.Translation = Vector3.Zero;
            button.Shadow = null;
        };
        button.PointerPressed += (_, _) =>
        {
            if (!button.IsEnabled)
            {
                return;
            }

            button.Translation = new Vector3(0, 0, 0);
        };
        button.PointerReleased += (_, _) =>
        {
            if (!button.IsEnabled)
            {
                return;
            }

            button.Shadow = new ThemeShadow();
            button.Translation = new Vector3(0, 0, state.Elevated ? 8 : 2);
        };
    }

    private sealed class ButtonInteractionState
    {
        public bool Elevated { get; set; }
    }

    public static TextBox ApplyTextInput(TextBox box)
    {
        box.CornerRadius = ControlCornerRadius;
        box.MinHeight = box.MinHeight > 0 ? box.MinHeight : 36;
        return box;
    }

    public static PasswordBox ApplyPasswordInput(PasswordBox box)
    {
        box.CornerRadius = ControlCornerRadius;
        box.MinHeight = box.MinHeight > 0 ? box.MinHeight : 36;
        return box;
    }

    public static ComboBox ApplyComboBox(ComboBox box)
    {
        box.CornerRadius = ControlCornerRadius;
        box.MinHeight = box.MinHeight > 0 ? box.MinHeight : 36;
        return box;
    }

    public static NumberBox ApplyNumberInput(NumberBox box)
    {
        box.CornerRadius = ControlCornerRadius;
        box.MinHeight = box.MinHeight > 0 ? box.MinHeight : 36;
        return box;
    }

    public static CheckBox ApplyCheckBox(CheckBox box)
    {
        box.CornerRadius = ControlCornerRadius;
        box.MinHeight = box.MinHeight > 0 ? box.MinHeight : 36;
        box.HorizontalAlignment = HorizontalAlignment.Stretch;
        return box;
    }

    public static ListView ApplyListView(ListView list)
    {
        list.Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        list.BorderThickness = new Thickness(0);
        list.Padding = new Thickness(0);
        list.HorizontalAlignment = HorizontalAlignment.Stretch;
        list.Resources["ListViewItemCornerRadius"] = ControlCornerRadius;
        list.Resources["ListViewItemCheckBoxCornerRadius"] = new CornerRadius(4);
        return list;
    }

    public static GridView ApplyGridView(GridView grid)
    {
        grid.Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        grid.BorderThickness = new Thickness(0);
        grid.Padding = new Thickness(0);
        grid.HorizontalAlignment = HorizontalAlignment.Stretch;
        grid.Resources["GridViewItemCornerRadius"] = ControlCornerRadius;
        grid.Resources["GridViewItemCheckBoxCornerRadius"] = new CornerRadius(4);
        return grid;
    }

    public static Slider ApplySlider(Slider slider)
    {
        slider.MinHeight = slider.MinHeight > 0 ? slider.MinHeight : 32;
        return slider;
    }

    public static Flyout ApplyFlyout(Flyout flyout)
    {
        var presenterStyle = new Style(typeof(FlyoutPresenter));
        presenterStyle.Setters.Add(new Setter(FlyoutPresenter.CornerRadiusProperty, ControlCornerRadius));
        presenterStyle.Setters.Add(new Setter(FlyoutPresenter.BackgroundProperty, OverlayControl));
        presenterStyle.Setters.Add(new Setter(FlyoutPresenter.BorderBrushProperty, Brush(0xFF, 0xFF, 0xFF, 0x24)));
        presenterStyle.Setters.Add(new Setter(FlyoutPresenter.BorderThicknessProperty, new Thickness(1)));
        flyout.FlyoutPresenterStyle = presenterStyle;
        return flyout;
    }

    public static MenuFlyout ApplyMenuFlyout(MenuFlyout flyout)
    {
        var presenterStyle = new Style(typeof(MenuFlyoutPresenter));
        presenterStyle.Setters.Add(new Setter(MenuFlyoutPresenter.CornerRadiusProperty, ControlCornerRadius));
        presenterStyle.Setters.Add(new Setter(MenuFlyoutPresenter.BackgroundProperty, Layer));
        presenterStyle.Setters.Add(new Setter(MenuFlyoutPresenter.BorderBrushProperty, Border));
        presenterStyle.Setters.Add(new Setter(MenuFlyoutPresenter.BorderThicknessProperty, new Thickness(1)));
        flyout.MenuFlyoutPresenterStyle = presenterStyle;
        return flyout;
    }

    public static ContentDialog ApplyContentDialog(ContentDialog dialog)
    {
        dialog.HorizontalAlignment = HorizontalAlignment.Center;
        dialog.VerticalAlignment = VerticalAlignment.Center;
        dialog.Resources["ContentDialogCornerRadius"] = ControlCornerRadius;
        dialog.Resources["OverlayCornerRadius"] = ControlCornerRadius;
        dialog.Resources["ControlCornerRadius"] = ControlCornerRadius;
        dialog.Resources["TextControlCornerRadius"] = ControlCornerRadius;
        dialog.Resources["ComboBoxItemCornerRadius"] = ControlCornerRadius;
        dialog.Resources["ListViewItemCornerRadius"] = ControlCornerRadius;
        dialog.Resources["GridViewItemCornerRadius"] = ControlCornerRadius;
        return dialog;
    }

    public static Thickness PagePadding(double width)
        => width < CompactBreakpoint ? new Thickness(18) : new Thickness(28);

    public static Thickness SpaciousPagePadding(double width)
        => width < CompactBreakpoint ? new Thickness(20) : new Thickness(40);
}

public enum FluentButtonStyle
{
    Standard,
    Accent,
    Subtle,
    Overlay,
    Danger,
}
