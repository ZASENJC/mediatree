using System;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace MediaTree.Windows.Views;

public sealed partial class LoginPage : Page
{
    private readonly TextBox _usernameBox = new();
    private readonly PasswordBox _passwordBox = new();
    private readonly TextBlock _errorText = new();
    private readonly Button _loginButton = new();

    public LoginPage()
    {
        BuildContent();
    }

    private void BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "LoginPage");

        var root = new Grid
        {
            Padding = new Thickness(48),
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };

        var stack = new StackPanel
        {
            MaxWidth = 420,
            Spacing = 18,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            VerticalAlignment = VerticalAlignment.Center,
        };

        stack.Children.Add(FluentTheme.Title("需要确认身份", 30));
        stack.Children.Add(FluentTheme.Body("这台电脑上的 MediaTree 已经设置过账号。输入一次用户名和密码后，桌面版会把登录状态安全保存到当前 Windows 用户里，下次会自动进入。", 14));

        _usernameBox.Header = "用户名";
        _usernameBox.KeyDown += OnLoginFieldKeyDown;
        AutomationProperties.SetAutomationId(_usernameBox, "LoginUsername");
        stack.Children.Add(_usernameBox);

        _passwordBox.Header = "密码";
        _passwordBox.KeyDown += OnLoginFieldKeyDown;
        AutomationProperties.SetAutomationId(_passwordBox, "LoginPassword");
        stack.Children.Add(_passwordBox);

        _errorText.Foreground = FluentTheme.Error;
        _errorText.TextWrapping = TextWrapping.Wrap;
        _errorText.Visibility = Visibility.Collapsed;
        AutomationProperties.SetAutomationId(_errorText, "LoginError");
        stack.Children.Add(_errorText);

        _loginButton.Content = "登录并记住这台电脑";
        FluentTheme.ApplyButton(_loginButton, FluentButtonStyle.Accent);
        _loginButton.MinWidth = 120;
        _loginButton.Click += async (_, _) => await SubmitLoginAsync();
        AutomationProperties.SetAutomationId(_loginButton, "LoginSubmit");
        stack.Children.Add(_loginButton);

        root.SizeChanged += (_, args) => root.Padding = FluentTheme.SpaciousPagePadding(args.NewSize.Width);
        Loaded += (_, _) => _usernameBox.Focus(FocusState.Programmatic);
        root.Children.Add(stack);
        Content = root;
    }

    private async void OnLoginFieldKeyDown(object sender, Microsoft.UI.Xaml.Input.KeyRoutedEventArgs args)
    {
        if (args.Key != global::Windows.System.VirtualKey.Enter)
        {
            return;
        }

        args.Handled = true;
        await SubmitLoginAsync();
    }

    private async System.Threading.Tasks.Task SubmitLoginAsync()
    {
        try
        {
            _loginButton.IsEnabled = false;
            _errorText.Visibility = Visibility.Collapsed;
            await Services.AppServices.Auth.LoginAndPersistAsync(_usernameBox.Text.Trim(), _passwordBox.Password);
            Services.AppServices.MainWindow?.NavigateToShell();
        }
        catch (Exception ex)
        {
            _errorText.Text = ex.Message;
            _errorText.Visibility = Visibility.Visible;
        }
        finally
        {
            _loginButton.IsEnabled = true;
        }
    }
}
