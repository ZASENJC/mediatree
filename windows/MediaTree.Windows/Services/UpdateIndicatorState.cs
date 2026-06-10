using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public static class UpdateIndicatorState
{
    public static bool ShouldShow(UpdateCheckResultDto? result)
        => result?.HasUpdate == true;
}
