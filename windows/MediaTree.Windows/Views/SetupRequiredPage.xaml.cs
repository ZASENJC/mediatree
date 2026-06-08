using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;

namespace MediaTree.Windows.Views;

public sealed partial class SetupRequiredPage : Page
{
    public SetupRequiredPage()
    {
        BuildContent();
    }

    private void BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "SetupRequiredPage");

        var root = new Grid
        {
            Padding = new Thickness(40),
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };

        var stack = new StackPanel
        {
            Spacing = 16,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        stack.Children.Add(FluentTheme.Title("先添加一个影片文件夹", 30));
        stack.Children.Add(FluentTheme.Body("媒体库还没有内容。请选择电脑上存放影片或剧集的文件夹，MediaTree 会自动整理后再显示媒体库和最近观看。", 15));

        var addButton = FluentTheme.ApplyButton(new Button
        {
            Content = "添加影片文件夹",
            HorizontalAlignment = HorizontalAlignment.Left,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(addButton, "SetupRequiredAddFolder");
        addButton.Click += (_, _) => ShellPage.Current?.NavigateToSetup();
        stack.Children.Add(addButton);

        root.Children.Add(FluentTheme.CenteredCard(stack, maxWidth: 580, padding: new Thickness(28)));
        Content = root;
    }
}
